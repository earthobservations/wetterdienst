# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for meteorological data provider."""

import datetime as dt
from zoneinfo import ZoneInfo

import polars as pl
import pytest
from polars.testing import assert_frame_equal

from wetterdienst.metadata.resolution import Resolution
from wetterdienst.provider.imgw.meteorology.api import (
    _STATUSLESS_COLUMNS,
    _STRUCTURAL_COLUMNS,
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
                "parameter": "temperature_air_mean_2m",
                "date": dt.datetime(2010, 8, 1, tzinfo=ZoneInfo("UTC")),
                "value": 20.6,
                "quality": None,
            },
            {
                "station_id": "253160090",
                "resolution": "daily",
                "dataset": "climate",
                "parameter": "temperature_air_min_0_05m",
                "date": dt.datetime(2010, 8, 1, tzinfo=ZoneInfo("UTC")),
                "value": 5.6,
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
                    "precipitation_height",
                    "snow_depth",
                    "temperature_air_max_2m",
                    "temperature_air_mean_2m",
                    "temperature_air_min_0_05m",
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
                "parameter": "humidity",
                "date": dt.datetime(2024, 1, 1, tzinfo=ZoneInfo("UTC")),
                "value": 0.905,
                "quality": None,
            },
            {
                "station_id": "354150100",
                "resolution": "daily",
                "dataset": "synop",
                "parameter": "precipitation_height",
                "date": dt.datetime(2024, 1, 1, tzinfo=ZoneInfo("UTC")),
                "value": 4.9,
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
                "parameter": "temperature_air_max_2m",
                "date": dt.datetime(2024, 1, 1, tzinfo=ZoneInfo("UTC")),
                "value": 5.3,
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
                "parameter": "temperature_air_min_0_05m",
                "date": dt.datetime(2024, 1, 1, tzinfo=ZoneInfo("UTC")),
                "value": 1.6,
                "quality": None,
            },
            {
                "station_id": "354150100",
                "resolution": "daily",
                "dataset": "synop",
                "parameter": "temperature_air_min_2m",
                "date": dt.datetime(2024, 1, 1, tzinfo=ZoneInfo("UTC")),
                "value": 3.5,
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
                    "humidity",
                    "precipitation_height",
                    "precipitation_height_day",
                    "precipitation_height_night",
                    "pressure_air_sea_level",
                    "pressure_air_site",
                    "pressure_vapor",
                    "temperature_air_max_2m",
                    "temperature_air_mean_2m",
                    "temperature_air_min_0_05m",
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


def test_imgw_meteorology_file_schema_names_are_declared_by_their_own_dataset() -> None:
    """Every column the rename map produces must be declared by the dataset it is read for.

    ``_parse_file`` renames raw ``column_N`` headers to ``name_original`` strings, and those are
    then matched against the dataset actually being requested -- so a name that only some *other*
    dataset declares is dropped exactly as silently as a misspelt one, and nothing upstream or in
    the suite notices. Comparing per dataset is what makes this bite: pooled over the provider,
    ``monthly/climate``'s ``maksymalna dobowa suma opadów`` passes because ``monthly/synop``
    declares it, which is how GH-1981 saw two entries where this found eight. Five of those eight
    were columns ``daily/synop`` read and never declared, closed by GH-1991, so the set is now
    empty: every column the parser renames is answerable by the dataset it is read for.

    This holds names, not positions -- a declared name sitting on the wrong ``column_N`` passes.
    ``test_imgw_meteorology_values_match_the_upstream_column`` covers that.
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
    assert undeclared == set()


# The Polish word for the aggregation a column carries, and the marker its canonical name has to
# have. Only min/max are listed: the canonical vocabulary marks a mean only for temperature, so
# `średnia dobowa prędkość wiatru` is plain `wind_speed` and a "mean" rule would be all noise.
_AGGREGATION_MARKERS = {
    "minimalna": "_min",
    "minimalne": "_min",
    "maksymalna": "_max",
    "maksymalne": "_max",
    "maksymalny": "_max",
}


def test_imgw_meteorology_parameters_agree_with_the_aggregation_their_name_states() -> None:
    """A column whose Polish name says minimum or maximum must not be declared as something else.

    The declarations are in a language this repository is not otherwise written in, so a canonical
    name can contradict the measurement it is attached to and read fine to everyone reviewing it.
    ``daily/climate`` published ``temperatura minimalna przy gruncie`` -- a nocturnal grass minimum
    -- as ``temperature_air_mean_0_05m`` for exactly that reason, while both ``monthly`` datasets
    declared the same quantity as ``temperature_air_min_0_05m`` (GH-1993).
    """
    mismatched = set()
    for resolution in ImgwMeteorologyMetadata:
        for dataset in resolution:
            for parameter in dataset.parameters:
                words = parameter.name_original.lower().split()
                for word in words:
                    marker = _AGGREGATION_MARKERS.get(word)
                    if marker is not None and marker not in parameter.name:
                        mismatched.add(
                            (resolution.name, dataset.name, parameter.name, parameter.name_original, marker),
                        )
    assert mismatched == set()


def test_imgw_meteorology_status_columns_do_not_collide_with_value_columns() -> None:
    """Test that the status column of a measurement is never itself a declared measurement.

    IMGW writes each status immediately after the value it belongs to, verified for all 61 declared
    columns against the ``*_format.txt`` files, so ``_parse_csv`` reads ``column_N+1`` as the
    status of ``column_N``. Declaring a value at ``column_N+1`` would make it both, and the parse
    resolves that by leaving ``column_N`` unstatused -- silently, and only for that one column.
    """
    colliding = set()
    for resolution, datasets in ImgwMeteorologyValues._file_schema.items():  # noqa: SLF001
        for dataset_name, files in datasets.items():
            for file_pattern, columns in files.items():
                values = {
                    int(column.removeprefix("column_"))
                    for column, name in columns.items()
                    if name not in {"station_id", "year", "month", "day"}
                }
                colliding |= {(resolution.value, dataset_name, file_pattern, n) for n in values if n + 1 in values}
    assert colliding == set()


# One `k_m_d` row -- PSZCZYNA, January 2010 -- filled in only where the test reads it. Field 25 is
# `PSDN`, the count of days with snow cover, and field 26 `DESD`, the count of days with rain; both
# are among the day counts the file ends with, and neither carries a status.
def _k_m_d_row(*, snow_cover_days: str, rain_days: str) -> bytes:
    fields = ["0"] * 27
    fields[0] = "249180010"
    fields[1] = "PSZCZYNA"
    fields[2] = "2010"
    fields[3] = "1"
    fields[24] = snow_cover_days
    fields[25] = rain_days
    return ",".join(fields).encode("latin-1")


# `PSDN` is not declared today. Declaring it is the thing the guard has to survive, so the test
# declares it here rather than waiting for the model to.
_PSDN_SCHEMA = {
    "column_1": "station_id",
    "column_3": "year",
    "column_4": "month",
    "column_25": "liczba dni z pokrywą śnieżną",
}


def test_imgw_meteorology_a_statusless_column_does_not_take_its_neighbour_for_a_status() -> None:
    """A column IMGW publishes with no status beside it must keep the value it holds.

    ``_parse_csv`` reads ``column_N+1`` as the status of ``column_N``, which holds for every column
    declared today but not for every column in the files: ``ROOP``, ``SGR``, the ``DN1``/``DN2`` days
    a monthly maximum fell on and the day counts ``k_m_d`` ends with have no status, and the field
    after them is another measurement. ``_STATUSLESS_COLUMNS`` names those positions so that
    declaring one does not silently start reading its neighbour as a status -- the failure would be
    confined to that one column and conditional on the neighbour's value, which is the kind that
    survives a review and a full remote suite (GH-1995).
    """
    values = ImgwMeteorologyValues._parse_csv(  # noqa: SLF001
        file=_k_m_d_row(snow_cover_days="12", rain_days="8"),
        station_id="249180010",
        resolution=Resolution.MONTHLY,
        schema=_PSDN_SCHEMA,
        statusless=_STATUSLESS_COLUMNS["k_m_d.*.csv"],
    )
    assert values.get_column("value").to_list() == [12.0]
    # The same row with the position not held statusless, which is what the parse did before: eight
    # days of rain is read as "brak pomiaru" and twelve days of snow cover are thrown away.
    unguarded = ImgwMeteorologyValues._parse_csv(  # noqa: SLF001
        file=_k_m_d_row(snow_cover_days="12", rain_days="8"),
        station_id="249180010",
        resolution=Resolution.MONTHLY,
        schema=_PSDN_SCHEMA,
        statusless=frozenset(),
    )
    assert unguarded.get_column("value").to_list() == [None]


def test_imgw_meteorology_statusless_columns_agree_with_the_file_schema() -> None:
    """Every statusless position must be keyed by a file the parser reads, and not be a status.

    ``_STATUSLESS_COLUMNS`` is keyed by the same regex strings as ``_file_schema``, so rewording one
    of those patterns leaves the entry behind with nothing to match and the guard silently off. The
    second half holds the other direction: a position declared statusless cannot also be the
    ``column_N+1`` the parse reads as some declared column's status, because the file cannot have it
    both ways.
    """
    patterns = {
        file_pattern
        for datasets in ImgwMeteorologyValues._file_schema.values()  # noqa: SLF001
        for files in datasets.values()
        for file_pattern in files
    }
    assert set(_STATUSLESS_COLUMNS) <= patterns
    contradicting = set()
    for resolution, datasets in ImgwMeteorologyValues._file_schema.items():  # noqa: SLF001
        for dataset_name, files in datasets.items():
            for file_pattern, columns in files.items():
                statusless = _STATUSLESS_COLUMNS.get(file_pattern, frozenset())
                values = {
                    int(column.removeprefix("column_"))
                    for column, name in columns.items()
                    if name not in _STRUCTURAL_COLUMNS
                }
                contradicting |= {
                    (resolution.value, dataset_name, file_pattern, n) for n in values if n + 1 in statusless
                }
    assert contradicting == set()


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


@pytest.mark.remote
@pytest.mark.parametrize(
    ("resolution", "dataset", "parameter", "station_id", "start_date", "expected"),
    [
        # These two read k_d column 17, PKSN, on the same day, and the file holds a literal "0" for
        # both. Only the status beside it separates them: PSZCZYNA carries "9", brak zjawiska --
        # there was no snow cover, so zero is the measurement -- and station 252190030 carries "8",
        # brak pomiaru. Nothing else in the row says which is which.
        ("daily", "climate", "snow_depth", "249180010", "2010-01-01", 0.0),
        ("daily", "climate", "snow_depth", "252190030", "2010-01-01", None),
        # A grass minimum of exactly 0.0 degrees on a January day, from `.0` beside a status of "8".
        ("daily", "climate", "temperature_air_min_0_05m", "249190090", "2010-01-01", None),
        # WARSZOWICE is a rain gauge and reports no snow: every row of o_d column 9 is "8" for it,
        # so the dataset used to answer 0 cm of snow cover for every day of a Polish January.
        ("daily", "precipitation", "snow_depth", "249180020", "2010-01-01", None),
        # 0 % relative humidity, from `.0` beside a status of "8" in k_m_t.
        ("monthly", "climate", "humidity", "249180010", "2010-01-01", None),
    ],
)
def test_imgw_meteorology_values_read_the_status_column(
    resolution: str,
    dataset: str,
    parameter: str,
    station_id: str,
    start_date: str,
    expected: float | None,
) -> None:
    """Test that a measurement IMGW marks as absent is not returned as a zero (GH-1994).

    Every value column is followed by a status column, and the value column of a missing
    measurement is not left empty -- it holds a literal ".0". So a station that measured nothing is
    indistinguishable from one that measured zero unless the status is read. "8" is brak pomiaru
    and has to become null; "9" is brak zjawiska, which is a true zero.
    """
    values = (
        ImgwMeteorologyRequest(
            parameters=[(resolution, dataset, parameter)],
            start_date=start_date,
            end_date=start_date,
        )
        .filter_by_station_id(station_id)
        .values.all()
        .df
    )
    if expected is None:
        assert values.is_empty(), f"{parameter} returned {values.get_column('value').to_list()}"
    else:
        assert values.get_column("value").to_list() == [expected]


@pytest.mark.remote
@pytest.mark.parametrize(
    ("parameter", "expected"),
    [
        ("temperature_air_max_2m", -4.2),
        ("temperature_air_min_2m", -5.4),
        ("temperature_air_min_0_05m", -5.4),
        ("precipitation_height", 0.0),
        ("snow_depth", 18.0),
    ],
)
def test_imgw_meteorology_daily_synop_returns_the_columns_it_reads(parameter: str, expected: float) -> None:
    """Test the five s_d columns daily/synop read and never declared (GH-1991).

    ``s_d_format.txt`` puts TMAX, TMIN, TMNG, SMDB and PKSN at columns 6, 8, 12, 14 and 17, the
    positions the file schema already renamed -- so no synop station could return a daily maximum
    or minimum temperature at all, nor its daily precipitation total or snow cover. The raw row for
    BIELSKO-BIALA on 2010-01-15 reads ``-4.2,"",-5.4,"",-4.9,"",-5.4,"",.0,"9","",18,""``, which
    also exercises GH-1994 in the other direction: SMDB is ``.0`` beside a status of "9", brak
    zjawiska, so zero is the measurement and stays.
    """
    values = (
        ImgwMeteorologyRequest(
            parameters=[("daily", "synop", parameter)],
            start_date="2010-01-15",
            end_date="2010-01-15",
        )
        .filter_by_station_id("349190600")
        .values.all()
        .df
    )
    assert values.get_column("value").to_list() == [expected]
