# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for meteorological data provider."""

import datetime as dt
from zoneinfo import ZoneInfo

import polars as pl
import pytest
from polars.testing import assert_frame_equal

from wetterdienst.provider.imgw.meteorology.api import (
    ImgwMeteorologyMetadata,
    ImgwMeteorologyRequest,
    ImgwMeteorologyValues,
)


@pytest.mark.remote
def test_imgw_meteorology_api_daily() -> None:
    """Test fetching of meteorological data."""
    request = ImgwMeteorologyRequest(
        parameters=[("daily", "klimat")],
        start_date="2010-08-01",
    ).filter_by_station_id("253160090")
    df_expected_station = pl.DataFrame(
        [
            {
                "resolution": "daily",
                "dataset": "climate",
                "station_id": "253160090",
                "start_date": None,
                "end_date": None,
                "latitude": 53.46,
                "longitude": 16.104444,
                "height": 137.0,
                "name": "WIERZCHOWO",
                "state": "Drawa (1888)",
            },
        ],
        schema={
            "resolution": pl.String,
            "dataset": pl.String,
            "station_id": pl.String,
            "start_date": pl.Datetime(time_zone="UTC"),
            "end_date": pl.Datetime(time_zone="UTC"),
            "latitude": pl.Float64,
            "longitude": pl.Float64,
            "height": pl.Float64,
            "name": pl.String,
            "state": pl.String,
        },
        orient="row",
    )
    assert_frame_equal(request.df, df_expected_station)
    values = request.values.all()
    df_expected_values = pl.DataFrame(
        [
            {
                "station_id": "253160090",
                "resolution": "daily",
                "dataset": "climate",
                "parameter": "cloud_cover_total",
                "date": dt.datetime(2010, 8, 1, tzinfo=ZoneInfo("UTC")),
                "value": 0.2875,
                "quality": None,
            },
            {
                "station_id": "253160090",
                "resolution": "daily",
                "dataset": "climate",
                "parameter": "humidity",
                "date": dt.datetime(2010, 8, 1, tzinfo=ZoneInfo("UTC")),
                "value": 0.0,
                "quality": None,
            },
            {
                "station_id": "253160090",
                "resolution": "daily",
                "dataset": "climate",
                "parameter": "precipitation_height",
                "date": dt.datetime(2010, 8, 1, tzinfo=ZoneInfo("UTC")),
                "value": 0.0,
                "quality": None,
            },
            {
                "station_id": "253160090",
                "resolution": "daily",
                "dataset": "climate",
                "parameter": "snow_depth",
                "date": dt.datetime(2010, 8, 1, tzinfo=ZoneInfo("UTC")),
                "value": 0.0,
                "quality": None,
            },
            {
                "station_id": "253160090",
                "resolution": "daily",
                "dataset": "climate",
                "parameter": "temperature_air_max_2m",
                "date": dt.datetime(2010, 8, 1, tzinfo=ZoneInfo("UTC")),
                "value": 28.2,
                "quality": None,
            },
            {
                "station_id": "253160090",
                "resolution": "daily",
                "dataset": "climate",
                "parameter": "temperature_air_mean_0_05m",
                "date": dt.datetime(2010, 8, 1, tzinfo=ZoneInfo("UTC")),
                "value": 5.6,
                "quality": None,
            },
            {
                "station_id": "253160090",
                "resolution": "daily",
                "dataset": "climate",
                "parameter": "temperature_air_mean_2m",
                "date": dt.datetime(2010, 8, 1, tzinfo=ZoneInfo("UTC")),
                "value": 20.6,
                "quality": None,
            },
            {
                "station_id": "253160090",
                "resolution": "daily",
                "dataset": "climate",
                "parameter": "temperature_air_min_2m",
                "date": dt.datetime(2010, 8, 1, tzinfo=ZoneInfo("UTC")),
                "value": 9.2,
                "quality": None,
            },
            {
                "station_id": "253160090",
                "resolution": "daily",
                "dataset": "climate",
                "parameter": "wind_speed",
                "date": dt.datetime(2010, 8, 1, tzinfo=ZoneInfo("UTC")),
                "value": 1.7,
                "quality": None,
            },
        ],
        schema={
            "station_id": pl.Enum(["253160090"]),
            "resolution": pl.Enum(["daily"]),
            "dataset": pl.Enum(["climate"]),
            "parameter": pl.Enum(
                [
                    "cloud_cover_total",
                    "humidity",
                    "precipitation_height",
                    "snow_depth",
                    "temperature_air_max_2m",
                    "temperature_air_mean_0_05m",
                    "temperature_air_mean_2m",
                    "temperature_air_min_2m",
                    "wind_speed",
                ]
            ),
            "date": pl.Datetime(time_zone="UTC"),
            "value": pl.Float64,
            "quality": pl.Float64,
        },
        orient="row",
    )
    assert_frame_equal(values.df, df_expected_values)


@pytest.mark.remote
def test_imgw_meteorology_api_monthly() -> None:
    """Test fetching of meteorological data."""
    request = ImgwMeteorologyRequest(
        parameters=[("monthly", "synop")],
        start_date="2010-08-01",
    ).filter_by_station_id("349190600")
    df_expected_station = pl.DataFrame(
        [
            {
                "resolution": "monthly",
                "dataset": "synop",
                "station_id": "349190600",
                "start_date": None,
                "end_date": None,
                "latitude": 49.806666666666665,
                "longitude": 19.002222222222223,
                "height": 396.0,
                "name": "Bielsko-Biała",
                "state": "Biała (2114)",
            },
        ],
        schema={
            "resolution": pl.String,
            "dataset": pl.String,
            "station_id": pl.String,
            "start_date": pl.Datetime(time_zone="UTC"),
            "end_date": pl.Datetime(time_zone="UTC"),
            "latitude": pl.Float64,
            "longitude": pl.Float64,
            "height": pl.Float64,
            "name": pl.String,
            "state": pl.String,
        },
        orient="row",
    )
    assert_frame_equal(request.df, df_expected_station)
    values = request.values.all()
    df_expected_values = pl.DataFrame(
        [
            {
                "station_id": "349190600",
                "resolution": "monthly",
                "dataset": "synop",
                "parameter": "cloud_cover_total",
                "date": dt.datetime(2010, 8, 1, tzinfo=ZoneInfo("UTC")),
                "value": 0.6,
                "quality": None,
            },
            {
                "station_id": "349190600",
                "resolution": "monthly",
                "dataset": "synop",
                "parameter": "humidity",
                "date": dt.datetime(2010, 8, 1, tzinfo=ZoneInfo("UTC")),
                "value": 0.753,
                "quality": None,
            },
            {
                "station_id": "349190600",
                "resolution": "monthly",
                "dataset": "synop",
                "parameter": "precipitation_height",
                "date": dt.datetime(2010, 8, 1, tzinfo=ZoneInfo("UTC")),
                "value": 204.1,
                "quality": None,
            },
            {
                "station_id": "349190600",
                "resolution": "monthly",
                "dataset": "synop",
                "parameter": "precipitation_height_day",
                "date": dt.datetime(2010, 8, 1, tzinfo=ZoneInfo("UTC")),
                "value": 136.4,
                "quality": None,
            },
            {
                "station_id": "349190600",
                "resolution": "monthly",
                "dataset": "synop",
                "parameter": "precipitation_height_max",
                "date": dt.datetime(2010, 8, 1, tzinfo=ZoneInfo("UTC")),
                "value": 92.3,
                "quality": None,
            },
            {
                "station_id": "349190600",
                "resolution": "monthly",
                "dataset": "synop",
                "parameter": "precipitation_height_night",
                "date": dt.datetime(2010, 8, 1, tzinfo=ZoneInfo("UTC")),
                "value": 67.7,
                "quality": None,
            },
            {
                "station_id": "349190600",
                "resolution": "monthly",
                "dataset": "synop",
                "parameter": "pressure_air_sea_level",
                "date": dt.datetime(2010, 8, 1, tzinfo=ZoneInfo("UTC")),
                "value": 1013.8,
                "quality": None,
            },
            {
                "station_id": "349190600",
                "resolution": "monthly",
                "dataset": "synop",
                "parameter": "pressure_air_site",
                "date": dt.datetime(2010, 8, 1, tzinfo=ZoneInfo("UTC")),
                "value": 967.4,
                "quality": None,
            },
            {
                "station_id": "349190600",
                "resolution": "monthly",
                "dataset": "synop",
                "parameter": "pressure_vapor",
                "date": dt.datetime(2010, 8, 1, tzinfo=ZoneInfo("UTC")),
                "value": 15.6,
                "quality": None,
            },
            {
                "station_id": "349190600",
                "resolution": "monthly",
                "dataset": "synop",
                "parameter": "snow_depth_max",
                "date": dt.datetime(2010, 8, 1, tzinfo=ZoneInfo("UTC")),
                "value": 0.0,
                "quality": None,
            },
            {
                "station_id": "349190600",
                "resolution": "monthly",
                "dataset": "synop",
                "parameter": "temperature_air_max_2m",
                "date": dt.datetime(2010, 8, 1, tzinfo=ZoneInfo("UTC")),
                "value": 29.5,
                "quality": None,
            },
            {
                "station_id": "349190600",
                "resolution": "monthly",
                "dataset": "synop",
                "parameter": "temperature_air_max_2m_mean",
                "date": dt.datetime(2010, 8, 1, tzinfo=ZoneInfo("UTC")),
                "value": 23.2,
                "quality": None,
            },
            {
                "station_id": "349190600",
                "resolution": "monthly",
                "dataset": "synop",
                "parameter": "temperature_air_mean_2m",
                "date": dt.datetime(2010, 8, 1, tzinfo=ZoneInfo("UTC")),
                "value": 18.2,
                "quality": None,
            },
            {
                "station_id": "349190600",
                "resolution": "monthly",
                "dataset": "synop",
                "parameter": "temperature_air_min_0_05m",
                "date": dt.datetime(2010, 8, 1, tzinfo=ZoneInfo("UTC")),
                "value": 7.7,
                "quality": None,
            },
            {
                "station_id": "349190600",
                "resolution": "monthly",
                "dataset": "synop",
                "parameter": "temperature_air_min_2m",
                "date": dt.datetime(2010, 8, 1, tzinfo=ZoneInfo("UTC")),
                "value": 8.5,
                "quality": None,
            },
            {
                "station_id": "349190600",
                "resolution": "monthly",
                "dataset": "synop",
                "parameter": "temperature_air_min_2m_mean",
                "date": dt.datetime(2010, 8, 1, tzinfo=ZoneInfo("UTC")),
                "value": 14.0,
                "quality": None,
            },
            {
                "station_id": "349190600",
                "resolution": "monthly",
                "dataset": "synop",
                "parameter": "wind_speed",
                "date": dt.datetime(2010, 8, 1, tzinfo=ZoneInfo("UTC")),
                "value": 3.1,
                "quality": None,
            },
        ],
        schema={
            "station_id": pl.Enum(["349190600"]),
            "resolution": pl.Enum(["monthly"]),
            "dataset": pl.Enum(["synop"]),
            "parameter": pl.Enum(
                [
                    "cloud_cover_total",
                    "humidity",
                    "precipitation_height",
                    "precipitation_height_day",
                    "precipitation_height_max",
                    "precipitation_height_night",
                    "pressure_air_sea_level",
                    "pressure_air_site",
                    "pressure_vapor",
                    "snow_depth_max",
                    "temperature_air_max_2m",
                    "temperature_air_max_2m_mean",
                    "temperature_air_mean_2m",
                    "temperature_air_min_0_05m",
                    "temperature_air_min_2m",
                    "temperature_air_min_2m_mean",
                    "wind_speed",
                ]
            ),
            "date": pl.Datetime(time_zone="UTC"),
            "value": pl.Float64,
            "quality": pl.Float64,
        },
        orient="row",
    )
    assert_frame_equal(values.df, df_expected_values)


@pytest.mark.remote
def test_imgw_meteorology_api_daily_synop() -> None:
    """Test fetching of daily synop data.

    Synop daily is archived per-station ("YYYY_<station-code>_s.zip"), not per-month like
    the other meteorology daily datasets, and needs its own file-selection logic in _get_urls().
    """
    request = ImgwMeteorologyRequest(
        parameters=[("daily", "synop")],
        start_date="2024-01-01",
        end_date="2024-01-01",
    ).filter_by_station_id("354150100")
    values = request.values.all()
    df_expected_values = pl.DataFrame(
        [
            {
                "station_id": "354150100",
                "resolution": "daily",
                "dataset": "synop",
                "parameter": "cloud_cover_total",
                "date": dt.datetime(2024, 1, 1, tzinfo=ZoneInfo("UTC")),
                "value": 0.0,
                "quality": None,
            },
            {
                "station_id": "354150100",
                "resolution": "daily",
                "dataset": "synop",
                "parameter": "humidity",
                "date": dt.datetime(2024, 1, 1, tzinfo=ZoneInfo("UTC")),
                "value": 0.905,
                "quality": None,
            },
            {
                "station_id": "354150100",
                "resolution": "daily",
                "dataset": "synop",
                "parameter": "precipitation_height_day",
                "date": dt.datetime(2024, 1, 1, tzinfo=ZoneInfo("UTC")),
                "value": 0.1,
                "quality": None,
            },
            {
                "station_id": "354150100",
                "resolution": "daily",
                "dataset": "synop",
                "parameter": "precipitation_height_night",
                "date": dt.datetime(2024, 1, 1, tzinfo=ZoneInfo("UTC")),
                "value": 4.8,
                "quality": None,
            },
            {
                "station_id": "354150100",
                "resolution": "daily",
                "dataset": "synop",
                "parameter": "pressure_air_sea_level",
                "date": dt.datetime(2024, 1, 1, tzinfo=ZoneInfo("UTC")),
                "value": 1004.2,
                "quality": None,
            },
            {
                "station_id": "354150100",
                "resolution": "daily",
                "dataset": "synop",
                "parameter": "pressure_air_site",
                "date": dt.datetime(2024, 1, 1, tzinfo=ZoneInfo("UTC")),
                "value": 1003.5,
                "quality": None,
            },
            {
                "station_id": "354150100",
                "resolution": "daily",
                "dataset": "synop",
                "parameter": "pressure_vapor",
                "date": dt.datetime(2024, 1, 1, tzinfo=ZoneInfo("UTC")),
                "value": 7.7,
                "quality": None,
            },
            {
                "station_id": "354150100",
                "resolution": "daily",
                "dataset": "synop",
                "parameter": "temperature_air_mean_2m",
                "date": dt.datetime(2024, 1, 1, tzinfo=ZoneInfo("UTC")),
                "value": 4.6,
                "quality": None,
            },
            {
                "station_id": "354150100",
                "resolution": "daily",
                "dataset": "synop",
                "parameter": "wind_speed",
                "date": dt.datetime(2024, 1, 1, tzinfo=ZoneInfo("UTC")),
                "value": 3.1,
                "quality": None,
            },
        ],
        schema={
            "station_id": pl.Enum(["354150100"]),
            "resolution": pl.Enum(["daily"]),
            "dataset": pl.Enum(["synop"]),
            "parameter": pl.Enum(
                [
                    "cloud_cover_total",
                    "humidity",
                    "precipitation_height_day",
                    "precipitation_height_night",
                    "pressure_air_sea_level",
                    "pressure_air_site",
                    "pressure_vapor",
                    "temperature_air_mean_2m",
                    "wind_speed",
                ]
            ),
            "date": pl.Datetime(time_zone="UTC"),
            "value": pl.Float64,
            "quality": pl.Float64,
        },
        orient="row",
    )
    assert_frame_equal(values.df, df_expected_values)


# columns the s_d file carries and the parser reads, but that daily/synop does not declare -- so
# they are renamed and then dropped. Upstream s_d_format.txt puts TMAX/TMIN/TMNG/SMDB/PKSN at
# exactly these positions, and k_d serves the same five under daily/climate, so the measurements
# are there and only the declaration is missing (GH-1991). Pinned rather than skipped: this set
# shrinking is the signal that the gap was closed.
_UNDECLARED_COLUMNS = frozenset(
    {
        ("daily", "synop", "s_d_[^t].*.csv", "column_6", "maksymalna temperatura dobowa"),
        ("daily", "synop", "s_d_[^t].*.csv", "column_8", "minimalna temperatura dobowa"),
        ("daily", "synop", "s_d_[^t].*.csv", "column_12", "temperatura minimalna przy gruncie"),
        ("daily", "synop", "s_d_[^t].*.csv", "column_14", "suma dobowa opadów"),
        ("daily", "synop", "s_d_[^t].*.csv", "column_17", "wysokość pokrywy śnieżnej"),
    },
)


def test_imgw_meteorology_file_schema_names_are_declared_by_their_own_dataset() -> None:
    """Every column the rename map produces must be declared by the dataset it is read for.

    ``_parse_file`` renames raw ``column_N`` headers to ``name_original`` strings, and those are
    then matched against the dataset actually being requested -- so a name that only some *other*
    dataset declares is dropped exactly as silently as a misspelt one, and nothing upstream or in
    the suite notices. Comparing per dataset is what makes this bite: pooled over the provider,
    ``monthly/climate``'s ``maksymalna dobowa suma opadów`` passes because ``monthly/synop``
    declares it, which is how GH-1981 saw two defects where there were four.
    """
    structural = {"station_id", "year", "month", "day"}
    undeclared = set()
    for resolution, datasets in ImgwMeteorologyValues._file_schema.items():  # noqa: SLF001
        for dataset_name, files in datasets.items():
            dataset = ImgwMeteorologyMetadata[resolution.value][dataset_name]
            declared = {parameter.name_original for parameter in dataset.parameters}
            for file_pattern, columns in files.items():
                for column, name_original in columns.items():
                    if name_original in structural or name_original in declared:
                        continue
                    undeclared.add((resolution.value, dataset_name, file_pattern, column, name_original))
    assert undeclared == _UNDECLARED_COLUMNS


@pytest.mark.remote
@pytest.mark.parametrize(
    ("resolution", "dataset", "station_id", "parameter", "expected"),
    [
        # k_m_d column 19 is OPMX, "maksymalna dobowa suma opadow w miesiacu"; monthly/climate had
        # declared it under o_m's name for MAXO ("opad maksymalny"), so even spelling the rename
        # correctly would not have matched. PSZCZYNA, a klimat station: January 2010, 17.8 mm.
        ("monthly", "climate", "249180010", "precipitation_height_max", 17.8),
        # s_m_d column 11 is TMNS; the rename map spelt it "minimalnaj". BIELSKO-BIALA, synop.
        ("monthly", "synop", "349190600", "temperature_air_min_2m_mean", 14.0),
        # o_d column 6 is SMDB, the daily precipitation total -- the reason the dataset exists. It
        # carried daily/climate's mean-temperature name. WARSZOWICE, an opad station.
        ("daily", "precipitation", "249180020", "precipitation_height", 1.1),
        # o_m field 9 is MAXO; field 7 is LDS, the count of days with snowfall. This one never
        # looked empty -- it published a day count as millimetres. WARSZOWICE, January 2010.
        ("monthly", "precipitation", "249180020", "precipitation_height_max", 17.8),
    ],
)
def test_imgw_meteorology_values_match_the_upstream_column(
    resolution: str,
    dataset: str,
    station_id: str,
    parameter: str,
    expected: float,
) -> None:
    """Test that parameters read the column their own dataset documents upstream (GH-1981)."""
    values = (
        ImgwMeteorologyRequest(
            parameters=[(resolution, dataset)],
            start_date="2010-01-01" if dataset != "synop" else "2010-08-01",
            end_date="2010-01-31" if dataset != "synop" else "2010-08-31",
        )
        .filter_by_station_id(station_id)
        .values.all()
        .df.filter(pl.col("parameter") == parameter)
        .sort("date")
    )
    assert not values.is_empty(), f"{resolution}/{dataset}/{parameter} returned no rows"
    assert values.get_column("value").item(0) == expected
