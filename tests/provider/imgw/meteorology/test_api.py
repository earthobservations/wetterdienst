# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for meteorological data provider."""

import datetime as dt
import zipfile
from io import BytesIO
from zoneinfo import ZoneInfo

import polars as pl
import pytest
from polars.testing import assert_frame_equal

from wetterdienst.exceptions import DownloadError
from wetterdienst.metadata.resolution import Resolution
from wetterdienst.provider.imgw.meteorology.api import (
    _ABSENT_DAY_NO_PHENOMENON,
    _STATUSLESS_COLUMNS,
    _STRUCTURAL_COLUMNS,
    ImgwMeteorologyMetadata,
    ImgwMeteorologyRequest,
    ImgwMeteorologyValues,
)
from wetterdienst.util.network import File


def _numbers(values: pl.DataFrame) -> pl.DataFrame:
    """Read the ``value`` column the reader hands over as the text of the file as the core reads it: a number."""
    return values.with_columns(pl.col("value").cast(pl.Float64, strict=False))


def test_imgw_meteorology_station_list_gives_no_region(monkeypatch: pytest.MonkeyPatch) -> None:
    """The river catchment of the station list is `river`, not `region` (GH-2019).

    The list's fourth column is `Rzeka`, the river catchment with its hydrographic code (`Odra (1)`, `Bałtyk (0)`
    for the sea), which the request read into `region`. The list gives no region.
    """
    catalogue = (
        "LP.;Kod 9-znakowy;Nazwa stacji;Rzeka;Rok założenia;Szerokość geograficzna;Długość geograficzna;"
        "Wysokość n.p.m.\r\n"
        "1;249170080;Dzierżkowice;Opawa (112);2024;49 59 32;17 50 47;270\r\n"
        "2;249180010;Pszczyna;Pszczynka (2116);1954;49 59 44;18 55 09;270\r\n"
        "4;249180030;Chałupki;Odra (1);1948;49 55 33;18 19 39;198\r\n"
    )
    monkeypatch.setattr(
        "wetterdienst.provider.imgw.meteorology.api.download_file",
        lambda **kwargs: File(url=kwargs["url"], content=BytesIO(catalogue.encode("utf8")), status=200),
    )

    df = ImgwMeteorologyRequest(parameters=[("daily", "climate")]).all().df

    assert df.select("station_id", "name", "river", "region", "elevation").rows() == [
        ("249170080", "Dzierżkowice", "Opawa (112)", None, 270.0),
        ("249180010", "Pszczyna", "Pszczynka (2116)", None, 270.0),
        ("249180030", "Chałupki", "Odra (1)", None, 198.0),
    ]
    assert df["region"].is_null().all()


def test_imgw_meteorology_station_list_returns_every_row(monkeypatch: pytest.MonkeyPatch) -> None:
    """The first station of the list is a station, not the header (GH-2650, GH-2752).

    The list has one header line. Skipping it and then reading the next row as the header lost
    `249170080` Dzierżkowice, the first row, so a request for it found nothing.
    """
    catalogue = (
        "LP.;Kod 9-znakowy;Nazwa stacji;Rzeka;Rok założenia;Szerokość geograficzna;Długość geograficzna;"
        "Wysokość n.p.m.\r\n"
        "1;249170080;Dzierżkowice;Opawa (112);2024;49 59 32;17 50 47;270\r\n"
        "2;249180010;Pszczyna;Pszczynka (2116);1954;49 59 44;18 55 09;270\r\n"
    )
    monkeypatch.setattr(
        "wetterdienst.provider.imgw.meteorology.api.download_file",
        lambda **kwargs: File(url=kwargs["url"], content=BytesIO(catalogue.encode("utf8")), status=200),
    )

    request = ImgwMeteorologyRequest(parameters=[("daily", "climate")])

    assert request.all().df["station_id"].to_list() == ["249170080", "249180010"]
    assert request.filter_by_station_id("249170080").df["name"].to_list() == ["Dzierżkowice"]


@pytest.mark.remote
def test_imgw_meteorology_api_daily() -> None:
    """Test fetching of meteorological data."""
    request = ImgwMeteorologyRequest(
        parameters=[("daily", "klimat")],
        start="2010-08-01",
    ).filter_by_station_id("253160090")
    df_expected_station = pl.DataFrame(
        [
            {
                "resolution": "daily",
                "dataset": "climate",
                "station_id": "253160090",
                "start_timestamp": None,
                "end_timestamp": None,
                "latitude": 53.46,
                "longitude": 16.104444,
                "elevation": 137.0,
                "name": "WIERZCHOWO",
                "region": None,
                "river": "Drawa (1888)",
            },
        ],
        schema={
            "resolution": pl.String,
            "dataset": pl.String,
            "station_id": pl.String,
            "start_timestamp": pl.Datetime(time_zone="UTC"),
            "end_timestamp": pl.Datetime(time_zone="UTC"),
            "latitude": pl.Float64,
            "longitude": pl.Float64,
            "elevation": pl.Float64,
            "name": pl.String,
            "region": pl.String,
            "river": pl.String,
        },
        orient="row",
    )
    assert_frame_equal(request.df, df_expected_station)
    values = request.values().all()
    df_expected_values = pl.DataFrame(
        [
            {
                "station_id": "253160090",
                "resolution": "daily",
                "dataset": "climate",
                "parameter": "cloud_cover_total_mean",
                "timestamp": dt.datetime(2010, 8, 1, tzinfo=ZoneInfo("UTC")),
                "value": 0.2875,
                "quality_flags": None,
            },
            {
                "station_id": "253160090",
                "resolution": "daily",
                "dataset": "climate",
                "parameter": "precipitation_amount",
                "timestamp": dt.datetime(2010, 8, 1, tzinfo=ZoneInfo("UTC")),
                "value": 0.0,
                "quality_flags": "9",
            },
            {
                "station_id": "253160090",
                "resolution": "daily",
                "dataset": "climate",
                "parameter": "snow_depth",
                "timestamp": dt.datetime(2010, 8, 1, tzinfo=ZoneInfo("UTC")),
                "value": 0.0,
                "quality_flags": "9",
            },
            {
                "station_id": "253160090",
                "resolution": "daily",
                "dataset": "climate",
                "parameter": "temperature_air_max_2m",
                "timestamp": dt.datetime(2010, 8, 1, tzinfo=ZoneInfo("UTC")),
                "value": 28.2,
                "quality_flags": None,
            },
            {
                "station_id": "253160090",
                "resolution": "daily",
                "dataset": "climate",
                "parameter": "temperature_air_mean_2m",
                "timestamp": dt.datetime(2010, 8, 1, tzinfo=ZoneInfo("UTC")),
                "value": 20.6,
                "quality_flags": None,
            },
            {
                "station_id": "253160090",
                "resolution": "daily",
                "dataset": "climate",
                "parameter": "temperature_air_min_0_05m",
                "timestamp": dt.datetime(2010, 8, 1, tzinfo=ZoneInfo("UTC")),
                "value": 5.6,
                "quality_flags": None,
            },
            {
                "station_id": "253160090",
                "resolution": "daily",
                "dataset": "climate",
                "parameter": "temperature_air_min_2m",
                "timestamp": dt.datetime(2010, 8, 1, tzinfo=ZoneInfo("UTC")),
                "value": 9.2,
                "quality_flags": None,
            },
            {
                "station_id": "253160090",
                "resolution": "daily",
                "dataset": "climate",
                "parameter": "wind_speed_mean",
                "timestamp": dt.datetime(2010, 8, 1, tzinfo=ZoneInfo("UTC")),
                "value": 1.7,
                "quality_flags": None,
            },
        ],
        schema={
            "station_id": pl.String,
            "resolution": pl.String,
            "dataset": pl.String,
            "parameter": pl.String,
            "timestamp": pl.Datetime(time_zone="UTC"),
            "value": pl.Float64,
            "quality_flags": pl.String,
        },
        orient="row",
    )
    assert_frame_equal(values.df, df_expected_values)


@pytest.mark.remote
def test_imgw_meteorology_api_monthly() -> None:
    """Test fetching of meteorological data."""
    request = ImgwMeteorologyRequest(
        parameters=[("monthly", "synop")],
        start="2010-08-01",
    ).filter_by_station_id("349190600")
    df_expected_station = pl.DataFrame(
        [
            {
                "resolution": "monthly",
                "dataset": "synop",
                "station_id": "349190600",
                "start_timestamp": None,
                "end_timestamp": None,
                "latitude": 49.806666666666665,
                "longitude": 19.002222222222223,
                "elevation": 396.0,
                "name": "Bielsko-Biała",
                "region": None,
                "river": "Biała (2114)",
            },
        ],
        schema={
            "resolution": pl.String,
            "dataset": pl.String,
            "station_id": pl.String,
            "start_timestamp": pl.Datetime(time_zone="UTC"),
            "end_timestamp": pl.Datetime(time_zone="UTC"),
            "latitude": pl.Float64,
            "longitude": pl.Float64,
            "elevation": pl.Float64,
            "name": pl.String,
            "region": pl.String,
            "river": pl.String,
        },
        orient="row",
    )
    assert_frame_equal(request.df, df_expected_station)
    values = request.values().all()
    df_expected_values = pl.DataFrame(
        [
            {
                "station_id": "349190600",
                "resolution": "monthly",
                "dataset": "synop",
                "parameter": "cloud_cover_total_mean",
                "timestamp": dt.datetime(2010, 8, 1, tzinfo=ZoneInfo("UTC")),
                "value": 0.6,
                "quality_flags": None,
            },
            {
                "station_id": "349190600",
                "resolution": "monthly",
                "dataset": "synop",
                "parameter": "humidity_relative_mean",
                "timestamp": dt.datetime(2010, 8, 1, tzinfo=ZoneInfo("UTC")),
                "value": 0.753,
                "quality_flags": None,
            },
            {
                "station_id": "349190600",
                "resolution": "monthly",
                "dataset": "synop",
                "parameter": "precipitation_amount",
                "timestamp": dt.datetime(2010, 8, 1, tzinfo=ZoneInfo("UTC")),
                "value": 204.1,
                "quality_flags": None,
            },
            {
                "station_id": "349190600",
                "resolution": "monthly",
                "dataset": "synop",
                "parameter": "precipitation_amount_day",
                "timestamp": dt.datetime(2010, 8, 1, tzinfo=ZoneInfo("UTC")),
                "value": 136.4,
                "quality_flags": None,
            },
            {
                "station_id": "349190600",
                "resolution": "monthly",
                "dataset": "synop",
                "parameter": "precipitation_amount_max",
                "timestamp": dt.datetime(2010, 8, 1, tzinfo=ZoneInfo("UTC")),
                "value": 92.3,
                "quality_flags": None,
            },
            {
                "station_id": "349190600",
                "resolution": "monthly",
                "dataset": "synop",
                "parameter": "precipitation_amount_night",
                "timestamp": dt.datetime(2010, 8, 1, tzinfo=ZoneInfo("UTC")),
                "value": 67.7,
                "quality_flags": None,
            },
            {
                "station_id": "349190600",
                "resolution": "monthly",
                "dataset": "synop",
                "parameter": "pressure_air_sea_level_mean",
                "timestamp": dt.datetime(2010, 8, 1, tzinfo=ZoneInfo("UTC")),
                "value": 1013.8,
                "quality_flags": None,
            },
            {
                "station_id": "349190600",
                "resolution": "monthly",
                "dataset": "synop",
                "parameter": "pressure_air_site_mean",
                "timestamp": dt.datetime(2010, 8, 1, tzinfo=ZoneInfo("UTC")),
                "value": 967.4,
                "quality_flags": None,
            },
            {
                "station_id": "349190600",
                "resolution": "monthly",
                "dataset": "synop",
                "parameter": "pressure_vapor_mean",
                "timestamp": dt.datetime(2010, 8, 1, tzinfo=ZoneInfo("UTC")),
                "value": 15.6,
                "quality_flags": None,
            },
            {
                "station_id": "349190600",
                "resolution": "monthly",
                "dataset": "synop",
                "parameter": "snow_depth_max",
                "timestamp": dt.datetime(2010, 8, 1, tzinfo=ZoneInfo("UTC")),
                "value": 0.0,
                "quality_flags": None,
            },
            {
                "station_id": "349190600",
                "resolution": "monthly",
                "dataset": "synop",
                "parameter": "temperature_air_max_2m",
                "timestamp": dt.datetime(2010, 8, 1, tzinfo=ZoneInfo("UTC")),
                "value": 29.5,
                "quality_flags": None,
            },
            {
                "station_id": "349190600",
                "resolution": "monthly",
                "dataset": "synop",
                "parameter": "temperature_air_max_2m_mean",
                "timestamp": dt.datetime(2010, 8, 1, tzinfo=ZoneInfo("UTC")),
                "value": 23.2,
                "quality_flags": None,
            },
            {
                "station_id": "349190600",
                "resolution": "monthly",
                "dataset": "synop",
                "parameter": "temperature_air_mean_2m",
                "timestamp": dt.datetime(2010, 8, 1, tzinfo=ZoneInfo("UTC")),
                "value": 18.2,
                "quality_flags": None,
            },
            {
                "station_id": "349190600",
                "resolution": "monthly",
                "dataset": "synop",
                "parameter": "temperature_air_min_0_05m",
                "timestamp": dt.datetime(2010, 8, 1, tzinfo=ZoneInfo("UTC")),
                "value": 7.7,
                "quality_flags": None,
            },
            {
                "station_id": "349190600",
                "resolution": "monthly",
                "dataset": "synop",
                "parameter": "temperature_air_min_2m",
                "timestamp": dt.datetime(2010, 8, 1, tzinfo=ZoneInfo("UTC")),
                "value": 8.5,
                "quality_flags": None,
            },
            {
                "station_id": "349190600",
                "resolution": "monthly",
                "dataset": "synop",
                "parameter": "temperature_air_min_2m_mean",
                "timestamp": dt.datetime(2010, 8, 1, tzinfo=ZoneInfo("UTC")),
                "value": 14.0,
                "quality_flags": None,
            },
            {
                "station_id": "349190600",
                "resolution": "monthly",
                "dataset": "synop",
                "parameter": "wind_speed_mean",
                "timestamp": dt.datetime(2010, 8, 1, tzinfo=ZoneInfo("UTC")),
                "value": 3.1,
                "quality_flags": None,
            },
        ],
        schema={
            "station_id": pl.String,
            "resolution": pl.String,
            "dataset": pl.String,
            "parameter": pl.String,
            "timestamp": pl.Datetime(time_zone="UTC"),
            "value": pl.Float64,
            "quality_flags": pl.String,
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
        start="2024-01-01",
        end="2024-01-01",
    ).filter_by_station_id("354150100")
    values = request.values().all()
    df_expected_values = pl.DataFrame(
        [
            {
                "station_id": "354150100",
                "resolution": "daily",
                "dataset": "synop",
                "parameter": "humidity_relative_mean",
                "timestamp": dt.datetime(2024, 1, 1, tzinfo=ZoneInfo("UTC")),
                "value": 0.905,
                "quality_flags": None,
            },
            {
                "station_id": "354150100",
                "resolution": "daily",
                "dataset": "synop",
                "parameter": "precipitation_amount",
                "timestamp": dt.datetime(2024, 1, 1, tzinfo=ZoneInfo("UTC")),
                "value": 4.9,
                "quality_flags": None,
            },
            {
                "station_id": "354150100",
                "resolution": "daily",
                "dataset": "synop",
                "parameter": "precipitation_amount_day",
                "timestamp": dt.datetime(2024, 1, 1, tzinfo=ZoneInfo("UTC")),
                "value": 0.1,
                "quality_flags": None,
            },
            {
                "station_id": "354150100",
                "resolution": "daily",
                "dataset": "synop",
                "parameter": "precipitation_amount_night",
                "timestamp": dt.datetime(2024, 1, 1, tzinfo=ZoneInfo("UTC")),
                "value": 4.8,
                "quality_flags": None,
            },
            {
                "station_id": "354150100",
                "resolution": "daily",
                "dataset": "synop",
                "parameter": "pressure_air_sea_level_mean",
                "timestamp": dt.datetime(2024, 1, 1, tzinfo=ZoneInfo("UTC")),
                "value": 1004.2,
                "quality_flags": None,
            },
            {
                "station_id": "354150100",
                "resolution": "daily",
                "dataset": "synop",
                "parameter": "pressure_air_site_mean",
                "timestamp": dt.datetime(2024, 1, 1, tzinfo=ZoneInfo("UTC")),
                "value": 1003.5,
                "quality_flags": None,
            },
            {
                "station_id": "354150100",
                "resolution": "daily",
                "dataset": "synop",
                "parameter": "pressure_vapor_mean",
                "timestamp": dt.datetime(2024, 1, 1, tzinfo=ZoneInfo("UTC")),
                "value": 7.7,
                "quality_flags": None,
            },
            {
                "station_id": "354150100",
                "resolution": "daily",
                "dataset": "synop",
                "parameter": "snow_depth",
                "timestamp": dt.datetime(2024, 1, 1, tzinfo=ZoneInfo("UTC")),
                "value": 0.0,
                "quality_flags": "9",
            },
            {
                "station_id": "354150100",
                "resolution": "daily",
                "dataset": "synop",
                "parameter": "temperature_air_max_2m",
                "timestamp": dt.datetime(2024, 1, 1, tzinfo=ZoneInfo("UTC")),
                "value": 5.3,
                "quality_flags": None,
            },
            {
                "station_id": "354150100",
                "resolution": "daily",
                "dataset": "synop",
                "parameter": "temperature_air_mean_2m",
                "timestamp": dt.datetime(2024, 1, 1, tzinfo=ZoneInfo("UTC")),
                "value": 4.6,
                "quality_flags": None,
            },
            {
                "station_id": "354150100",
                "resolution": "daily",
                "dataset": "synop",
                "parameter": "temperature_air_min_0_05m",
                "timestamp": dt.datetime(2024, 1, 1, tzinfo=ZoneInfo("UTC")),
                "value": 1.6,
                "quality_flags": None,
            },
            {
                "station_id": "354150100",
                "resolution": "daily",
                "dataset": "synop",
                "parameter": "temperature_air_min_2m",
                "timestamp": dt.datetime(2024, 1, 1, tzinfo=ZoneInfo("UTC")),
                "value": 3.5,
                "quality_flags": None,
            },
            {
                "station_id": "354150100",
                "resolution": "daily",
                "dataset": "synop",
                "parameter": "wind_speed_mean",
                "timestamp": dt.datetime(2024, 1, 1, tzinfo=ZoneInfo("UTC")),
                "value": 3.1,
                "quality_flags": None,
            },
        ],
        schema={
            "station_id": pl.String,
            "resolution": pl.String,
            "dataset": pl.String,
            "parameter": pl.String,
            "timestamp": pl.Datetime(time_zone="UTC"),
            "value": pl.Float64,
            "quality_flags": pl.String,
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
    undeclared = set()
    for resolution, datasets in ImgwMeteorologyValues._file_schema.items():  # noqa: SLF001
        for dataset_name, files in datasets.items():
            dataset = ImgwMeteorologyMetadata[resolution.value][dataset_name]
            declared = {parameter.name_original for parameter in dataset.parameters}
            for file_pattern, columns in files.items():
                for column, name_original in columns.items():
                    if name_original in _STRUCTURAL_COLUMNS or name_original in declared:
                        continue
                    undeclared.add((resolution.value, dataset_name, file_pattern, column, name_original))
    assert undeclared == set()


# The Polish word for the aggregation a column carries, and the marker its canonical name has to
# have. Only min/max are listed: the mean (`średnia dobowa prędkość wiatru` is `wind_speed_mean`) is held for every
# quantity the rule of GH-3151 has been applied to by `tests/metadata/test_mean_names.py`, which reads `średni*` too.
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
                    if name not in _STRUCTURAL_COLUMNS
                }
                colliding |= {(resolution.value, dataset_name, file_pattern, n) for n in values if n + 1 in values}
    assert colliding == set()


# One `o_d` row per status, for the same column: field 6 is `SMDB`, the daily precipitation total,
# and field 7 its status. The other fields are filled only far enough to be read.
def _o_d_rows(cases: list[tuple[str, str]]) -> bytes:
    rows = []
    for day, (value, status) in enumerate(cases, start=1):
        fields = [""] * 16
        fields[0] = "249180020"
        fields[1] = "WARSZOWICE"
        fields[2] = "2024"
        fields[3] = "07"
        fields[4] = f"{day:02d}"
        fields[5] = value
        fields[6] = status
        rows.append(",".join(fields))
    return "\n".join(rows).encode("latin-1")


_SMDB_SCHEMA = {
    "column_1": "station_id",
    "column_3": "year",
    "column_4": "month",
    "column_5": "day",
    "column_6": "suma dobowa opadów",
}


def test_imgw_meteorology_reads_every_status_the_files_document() -> None:
    """Each status has to reach the value and the quality flags column, including an empty value cell.

    The files do not write a status the same way twice. Where the status is "8" the value cell holds
    a literal ".0" -- the reason the status has to be read at all -- but where it is "9",
    ``o_d_01_2024`` writes ".0" and ``o_d_07_2024`` leaves the cell empty, for the same parameter
    three files apart. Passing the cell through therefore returned no value for a day IMGW documents
    as having had no precipitation, so "9" is written as the zero it means (GH-1997).

    The status itself is carried verbatim into ``quality_flags``, which the provider used to return null
    throughout (GH-1998). "8", "9" and ``Z`` are IMGW's own codes. ``Z``, *opad zbiorczy*, is a sum over
    the preceding days that were not measured: the value is kept, because it is a real measurement, and
    the ``Z`` says it does not belong to this date alone (it was mapped to the number 10 while the column
    was numeric, GH-2757).
    """
    values = ImgwMeteorologyValues._parse_csv(  # noqa: SLF001
        file=_o_d_rows([("1.2", ""), (".0", "8"), ("", "9"), ("7.4", "Z")]),
        station_id="249180020",
        resolution=Resolution.DAILY,
        schema=_SMDB_SCHEMA,
    )
    assert _numbers(values).get_column("value").to_list() == [1.2, None, 0.0, 7.4]
    assert values.get_column("quality_flags").to_list() == [None, "8", "9", "Z"]


@pytest.mark.remote
@pytest.mark.parametrize(
    ("dataset", "parameter", "station_id", "start_date"),
    [
        # o_d for July 2024 leaves the value cell empty beside its "9"s: WARSZOWICE reported no rain
        # on the 2nd, which came back as no value at all rather than 0.0 mm.
        ("precipitation", "precipitation_amount", "249180020", "2024-07-02"),
        # the same in s_d, for a parameter that is zero all winter: no snow cover on New Year's Day.
        ("synop", "snow_depth", "354150100", "2024-01-01"),
    ],
)
def test_imgw_meteorology_brak_zjawiska_is_a_zero_even_when_the_cell_is_empty(
    dataset: str,
    parameter: str,
    station_id: str,
    start_date: str,
) -> None:
    """A documented *brak zjawiska* has to be the zero it means, not a missing value (GH-1997)."""
    values = (
        ImgwMeteorologyRequest(
            parameters=[("daily", dataset, parameter)],
            start=start_date,
            end=start_date,
        )
        .filter_by_station_id(station_id)
        .values()
        .all()
        .df
    )
    assert values.get_column("value").to_list() == [0.0]
    assert values.get_column("quality_flags").to_list() == ["9"]


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
    assert _numbers(values).get_column("value").to_list() == [12.0]
    # The same row with the position not held statusless, which is what the parse did before: eight
    # days of rain is read as "brak pomiaru" and twelve days of snow cover are thrown away.
    unguarded = ImgwMeteorologyValues._parse_csv(  # noqa: SLF001
        file=_k_m_d_row(snow_cover_days="12", rain_days="8"),
        station_id="249180010",
        resolution=Resolution.MONTHLY,
        schema=_PSDN_SCHEMA,
        statusless=frozenset(),
    )
    assert _numbers(unguarded).get_column("value").to_list() == [None]


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
        ("monthly", "climate", "249180010", "precipitation_amount_max", 17.8),
        # s_m_d column 11 is TMNS; the rename map spelt it "minimalnaj". BIELSKO-BIALA, synop.
        ("monthly", "synop", "349190600", "temperature_air_min_2m_mean", 14.0),
        # o_d column 6 is SMDB, the daily precipitation total -- the reason the dataset exists. It
        # carried daily/climate's mean-temperature name. WARSZOWICE, an opad station.
        ("daily", "precipitation", "249180020", "precipitation_amount", 1.1),
        # o_m field 9 is MAXO; field 7 is LDS, the count of days with snowfall. This one never
        # looked empty -- it published a day count as millimetres. WARSZOWICE, January 2010.
        ("monthly", "precipitation", "249180020", "precipitation_amount_max", 17.8),
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
            start="2010-01-01" if dataset != "synop" else "2010-08-01",
            end="2010-01-31" if dataset != "synop" else "2010-08-31",
        )
        .filter_by_station_id(station_id)
        .values()
        .all()
        .df.filter(pl.col("parameter") == parameter)
        .sort("timestamp")
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
        ("monthly", "climate", "humidity_relative_mean", "249180010", "2010-01-01", None),
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
            start=start_date,
            end=start_date,
        )
        .filter_by_station_id(station_id)
        .values()
        .all()
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
        ("precipitation_amount", 0.0),
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
            start="2010-01-15",
            end="2010-01-15",
        )
        .filter_by_station_id("349190600")
        .values()
        .all()
        .df
    )
    assert values.get_column("value").to_list() == [expected]


# `o_d` rows for February 2010, as (station, day, SMDB, its status): field 6 is `SMDB` and field 7 its
# status, and `PKSN` and `HSS`, fields 9 and 11, carry "8" -- not measured -- in their status fields
# 10 and 12, the way WARSZOWICE's do in every row of `o_d_02_2010`.
def _o_d_zip(rows: list[tuple[str, int, str, str]]) -> File:
    lines = []
    for station_id, day, value, status in rows:
        fields = [""] * 16
        fields[0] = station_id
        fields[2] = "2010"
        fields[3] = "02"
        fields[4] = f"{day:02d}"
        fields[5] = value
        fields[6] = status
        fields[8] = "0"
        fields[9] = "8"
        fields[10] = "0"
        fields[11] = "8"
        lines.append(",".join(fields))
    content = BytesIO()
    with zipfile.ZipFile(content, "w") as archive:
        archive.writestr("o_d_02_2010.csv", "\n".join(lines).encode("latin-1"))
    content.seek(0)
    return File(url="https://example.invalid/2010_02_o.zip", content=content, status=200)


def test_imgw_meteorology_a_day_absent_from_a_present_month_is_no_precipitation() -> None:
    """A day ``o_d`` leaves out of a month the station reports in is a dry day (GH-2000).

    ``o_d_format.txt`` says so -- "Brak zjawiska to również brak dnia w istniejącym miesiącu" -- and
    the older files rely on it, while the newer ones write the same days out with status "9". So the
    series of one rain gauge read 0 mm or nothing for a dry day depending on the year of the file.
    Only ``SMDB`` is filled: ``PKSN`` and ``HSS`` are "8" in the rows that are there, and a dry day
    says nothing about snow cover. A day written with "8" stays a missing measurement, and the filled
    days carry 11 rather than IMGW's 9, since no status in the file says so.
    """
    values = ImgwMeteorologyValues._parse_file(  # noqa: SLF001
        ImgwMeteorologyValues.__new__(ImgwMeteorologyValues),
        file=_o_d_zip(
            [
                ("249180020", 1, ".2", ""),
                ("249180020", 3, "2.1", ""),
                ("249180020", 5, ".0", "8"),
                # another station's rows do not make a month present for this one
                ("250000000", 2, "4.0", ""),
            ],
        ),
        station_id="249180020",
        resolution=Resolution.DAILY,
        file_schema=ImgwMeteorologyValues._file_schema[Resolution.DAILY]["precipitation"],  # noqa: SLF001
    ).sort("parameter", "timestamp")
    precipitation = values.filter(pl.col("parameter") == "suma dobowa opadów")
    assert precipitation.get_column("timestamp").dt.strftime("%Y-%m-%d").to_list() == [
        f"2010-02-{day:02d}" for day in range(1, 29)
    ]
    assert _numbers(precipitation).get_column("value").to_list()[:6] == [0.2, 0.0, 2.1, 0.0, None, 0.0]
    assert precipitation.get_column("quality_flags").to_list()[:6] == [None, "11", None, "11", "8", "11"]
    assert set(_numbers(precipitation).get_column("value").to_list()[6:]) == {0.0}
    assert set(precipitation.get_column("quality_flags").to_list()[6:]) == {"11"}
    # the snow columns keep only the rows the file has
    assert values.filter(pl.col("parameter") != "suma dobowa opadów").height == 6
    # a station with no row in the month gets none either
    absent_station = ImgwMeteorologyValues._parse_file(  # noqa: SLF001
        ImgwMeteorologyValues.__new__(ImgwMeteorologyValues),
        file=_o_d_zip([("250000000", 2, "4.0", "")]),
        station_id="249180020",
        resolution=Resolution.DAILY,
        file_schema=ImgwMeteorologyValues._file_schema[Resolution.DAILY]["precipitation"],  # noqa: SLF001
    )
    assert absent_station.is_empty()


def test_imgw_meteorology_absent_day_columns_agree_with_the_file_schema() -> None:
    """Every entry of ``_ABSENT_DAY_NO_PHENOMENON`` must name a file and a column the parser reads.

    It is keyed by the same regex strings as ``_file_schema``, so rewording a pattern, or renaming
    the column, would leave the entry with nothing to match and the dry days quietly absent again.
    """
    schemas = {
        file_pattern: set(columns.values())
        for datasets in ImgwMeteorologyValues._file_schema.values()  # noqa: SLF001
        for files in datasets.values()
        for file_pattern, columns in files.items()
    }
    for file_pattern, names in _ABSENT_DAY_NO_PHENOMENON.items():
        assert file_pattern in schemas
        assert names <= schemas[file_pattern]


@pytest.mark.remote
def test_imgw_meteorology_daily_precipitation_returns_a_dry_day_the_file_leaves_out() -> None:
    """WARSZOWICE has no row for 2010-02-16 in ``o_d_02_2010``: a dry day, returned as 0 mm (GH-2000)."""
    values = (
        ImgwMeteorologyRequest(
            parameters=[("daily", "precipitation", "precipitation_amount")],
            start="2010-02-16",
            end="2010-02-16",
        )
        .filter_by_station_id("249180020")
        .values()
        .all()
        .df
    )
    assert values.get_column("value").to_list() == [0.0]
    assert values.get_column("quality_flags").to_list() == ["11"]


def test_imgw_meteorology_raises_a_failed_download_and_drops_a_missing_file(monkeypatch: pytest.MonkeyPatch) -> None:
    """A download that failed for any reason but a 404 is raised, not dropped as a missing file (GH-2430)."""
    from types import SimpleNamespace  # noqa: PLC0415

    from wetterdienst import Settings  # noqa: PLC0415
    from wetterdienst.provider.imgw.meteorology import api as imgw_meteorology_api  # noqa: PLC0415

    missing = File(url="https://example.invalid/missing.zip", content=FileNotFoundError("missing.zip"), status=404)
    failed = File(url="https://example.invalid/a.zip", content=ConnectionError("503"), status=503)
    values = ImgwMeteorologyValues.__new__(ImgwMeteorologyValues)
    values.sr = SimpleNamespace(request=SimpleNamespace(settings=Settings()))  # ty: ignore[invalid-assignment]
    monkeypatch.setattr(values, "_get_urls", lambda _dataset, _station_id: ["unused"])
    dataset = ImgwMeteorologyMetadata.daily.climate
    monkeypatch.setattr(imgw_meteorology_api, "download_files", lambda **_kwargs: [missing, failed])
    with pytest.raises(DownloadError):
        values._collect_station_parameter_or_dataset("249180010", dataset)  # noqa: SLF001
    monkeypatch.setattr(imgw_meteorology_api, "download_files", lambda **_kwargs: [missing])
    assert values._collect_station_parameter_or_dataset("249180010", dataset).is_empty()  # noqa: SLF001


# Rows copied from the live monthly zips of daily/climate, KRAKÓW-OBSERWATORIUM: `k_d` of
# 2024_05_k.zip and 2025_01_k.zip, and the pair of 2024_04_k.zip. The zips of May 2024 onwards hold
# `k_d` alone; `k_d_t` (humidity, wind speed, cloud cover) is no longer published (GH-2819). Likewise
# `s_d_t` of daily/synop, last written in 2024_375_s.zip for June 2024: `2025_375_s.zip` holds `s_d` alone.
_K_D_APRIL_2024 = '"250190390","KRAKÓW-OBSERWATORIUM","2024","04","01",26.4,"",10.9,"",18.6,"",5.5,"",10.0,"","W",0,"9"'
_K_D_T_APRIL_2024 = '"250190390","KRAKÓW-OBSERWATORIUM","2024","04","01",18.6,"",60.5,"",1.7,"",7.3,""'
_K_D_MAY_2024 = '"250190390","KRAKÓW-OBSERWATORIUM          ","2024","05","01",24.1,,8.8,,16.5,,6.4,,,"9",,,"9"'
_S_D_JANUARY_2025 = (
    '"352200375",WARSZAWA,"2025","01","01",6.5,,-1.8,,3.8,,-4.5,,,"9",,,"9",,"9",0.1,,,"9",,"9",,"9",,"9",,"9",,"9",,"9",'
    ',"9",,"9",,"9",,"9",,"9",,"9",,"9",,"9",0,,0,,R,"11",,"04",,,"8"'
)
_K_D_JANUARY_2025 = '"250190390","KRAKÓW-OBSERWATORIUM          ","2025","01","02",11.3,,0.7,,5.1,,-3.9,,6.1,,"S",,"9"'


def _zip(files: dict[str, str]) -> File:
    content = BytesIO()
    with zipfile.ZipFile(content, "w") as archive:
        for name, line in files.items():
            archive.writestr(name, line.encode("latin-1"))
    content.seek(0)
    return File(url="https://example.invalid/imgw.zip", content=content, status=200)


def _read_daily(dataset: str, files: dict[str, str]) -> dict[str, tuple[float | None, str | None]]:
    values = ImgwMeteorologyValues._parse_file(  # noqa: SLF001
        ImgwMeteorologyValues.__new__(ImgwMeteorologyValues),
        file=_zip(files),
        station_id="250190390" if dataset == "climate" else "352200375",
        resolution=Resolution.DAILY,
        file_schema=ImgwMeteorologyValues._file_schema[Resolution.DAILY][dataset],  # noqa: SLF001
    )
    return {row["parameter"]: (row["value"], row["quality_flags"]) for row in _numbers(values).iter_rows(named=True)}


def test_imgw_meteorology_daily_climate_reads_a_zip_without_k_d_t() -> None:
    """The zips from May 2024 hold only ``k_d``: its columns are read, ``k_d_t``'s are absent (GH-2819)."""
    may = _read_daily("climate", {"k_d_05_2024.csv": _K_D_MAY_2024})
    assert may == {
        "maksymalna temperatura dobowa": (24.1, None),
        "minimalna temperatura dobowa": (8.8, None),
        "średnia dobowa temperatura": (16.5, None),
        "temperatura minimalna przy gruncie": (6.4, None),
        "suma dobowa opadów": (0.0, "9"),
        "wysokość pokrywy śnieżnej": (0.0, "9"),
    }
    january = _read_daily("climate", {"k_d_01_2025.csv": _K_D_JANUARY_2025})
    assert january["suma dobowa opadów"] == (6.1, None)
    assert january["średnia dobowa temperatura"] == (5.1, None)


def test_imgw_meteorology_daily_synop_reads_a_zip_without_s_d_t() -> None:
    """The synop zips from July 2024 hold only ``s_d``, the same way (GH-2819)."""
    january = _read_daily("synop", {"s_d_375_2025.csv": _S_D_JANUARY_2025})
    assert january == {
        "maksymalna temperatura dobowa": (6.5, None),
        "minimalna temperatura dobowa": (-1.8, None),
        "średnia dobowa temperatura": (3.8, None),
        "temperatura minimalna przy gruncie": (-4.5, None),
        "suma dobowa opadów": (0.0, "9"),
        "wysokość pokrywy śnieżnej": (0.0, "9"),
    }


def test_imgw_meteorology_daily_climate_still_reads_k_d_t_where_the_zip_holds_it() -> None:
    """Up to April 2024 the zip holds both files, and ``k_d_t``'s humidity, wind and cloud cover are read."""
    april = _read_daily("climate", {"k_d_04_2024.csv": _K_D_APRIL_2024, "k_d_t_04_2024.csv": _K_D_T_APRIL_2024})
    assert april["średnia dobowa wilgotność względna"] == (60.5, None)
    assert april["średnia dobowa prędkość wiatru"] == (1.7, None)
    assert april["średnie dobowe zachmurzenie ogólne"] == (7.3, None)
    assert april["maksymalna temperatura dobowa"] == (26.4, None)
    assert april["suma dobowa opadów"] == (10.0, None)
    # `k_d_t` is read first, and keeps the mean temperature both files carry
    assert april["średnia dobowa temperatura"] == (18.6, None)


@pytest.mark.remote
def test_imgw_meteorology_daily_climate_across_the_end_of_k_d_t() -> None:
    """A year that spans April and May 2024 returns every day, as the issue's request raised before (GH-2819)."""
    values = (
        ImgwMeteorologyRequest(
            parameters=[("daily", "climate", "precipitation_amount")],
            start="2024-01-01",
            end="2024-12-31",
        )
        .filter_by_station_id("250190390")
        .values()
        .all()
        .df
    )
    assert values.height == 366


def _meteorology_urls(
    monkeypatch: pytest.MonkeyPatch, resolution: str, files: list[str], start: dt.datetime, end: dt.datetime
) -> list[str]:
    """Run the file selection of ``_get_urls`` on a listing, for a window of UTC instants."""
    from types import SimpleNamespace  # noqa: PLC0415

    from wetterdienst import Settings  # noqa: PLC0415
    from wetterdienst.provider.imgw.meteorology import api as imgw_meteorology_api  # noqa: PLC0415

    values = ImgwMeteorologyValues.__new__(ImgwMeteorologyValues)
    values.sr = SimpleNamespace(start=start, end=end, settings=Settings())  # ty: ignore[invalid-assignment]
    monkeypatch.setattr(imgw_meteorology_api, "list_files_for_interval", lambda *_args, **_kwargs: files)
    dataset = getattr(ImgwMeteorologyMetadata, resolution).climate
    return [url.rsplit("/", 1)[-1] for url in values._get_urls(dataset, "249180010")]  # noqa: SLF001


def _utc(*args: int) -> dt.datetime:
    return dt.datetime(*args, tzinfo=ZoneInfo("UTC"))


@pytest.mark.parametrize(
    ("start", "end", "expected"),
    [
        # a file named by the year covers it, one named by year and month covers that month, both ends included
        (_utc(2023, 5, 31), _utc(2023, 6, 2), ["2023_k.zip", "2023_05_k.zip"]),
        (_utc(2023, 4, 30, 23), _utc(2023, 4, 30, 23), ["2023_k.zip"]),
        (_utc(2023, 12, 31), _utc(2024, 1, 1), ["2023_k.zip", "2024_01_k.zip"]),
        (_utc(2022, 12, 31), _utc(2022, 12, 31), []),
    ],
)
def test_imgw_meteorology_daily_files_are_selected_by_the_period_their_name_gives(
    monkeypatch: pytest.MonkeyPatch, start: dt.datetime, end: dt.datetime, expected: list[str]
) -> None:
    """Test that a daily file is kept when the year or month of its name overlaps the window."""
    names = ["2023_k.zip", "2023_05_k.zip", "2024_01_k.zip", "k_d_format.txt", "?C=D;O=A"]
    files = [f"https://example.invalid/{name}" for name in names]
    assert _meteorology_urls(monkeypatch, "daily", files, start, end) == expected


@pytest.mark.parametrize(
    ("start", "end", "expected"),
    [
        # "1951_m_k.zip" is one year, "1951_1955_m_k.zip" the years from the first to the second, included
        (_utc(1955, 6, 1), _utc(1956, 1, 1), ["1951_1955_m_k.zip", "1956_1960_m_k.zip"]),
        (_utc(1951, 12, 31), _utc(1951, 12, 31), ["1951_m_k.zip", "1951_1955_m_k.zip"]),
        (_utc(1961, 1, 1), _utc(1961, 1, 1), ["1961_m_k.zip"]),
        (_utc(1962, 1, 1), _utc(1962, 1, 1), []),
    ],
)
def test_imgw_meteorology_monthly_files_are_selected_by_the_years_their_name_gives(
    monkeypatch: pytest.MonkeyPatch, start: dt.datetime, end: dt.datetime, expected: list[str]
) -> None:
    """Test that a monthly file is kept when the years of its name overlap the window."""
    names = ["1951_m_k.zip", "1951_1955_m_k.zip", "1956_1960_m_k.zip", "1961_m_k.zip", "k_m_t_format.txt"]
    files = [f"https://example.invalid/{name}" for name in names]
    assert _meteorology_urls(monkeypatch, "monthly", files, start, end) == expected


def test_imgw_meteorology_a_file_name_without_a_period_is_an_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that a name the period cannot be read from is reported, not left out with its data."""
    files = ["https://example.invalid/2023_k.zip", "https://example.invalid/abcd_k.zip"]
    with pytest.raises(ValueError, match=r"abcd_k\.zip"):
        _meteorology_urls(monkeypatch, "daily", files, _utc(2023, 1, 1), _utc(2023, 2, 1))
