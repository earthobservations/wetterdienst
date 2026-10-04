# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for export of timeseries data."""

import contextlib
import datetime as dt
import json
import logging
import math
import re
import sqlite3
import sys
from pathlib import Path
from unittest import mock
from zoneinfo import ZoneInfo

import polars as pl
import pytest

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover
    import tomli as tomllib

from tests.conftest import IS_CI, IS_WINDOWS
from wetterdienst import Settings
from wetterdienst.exceptions import ExportRefusedError
from wetterdienst.io.export import ExportMixin
from wetterdienst.metadata.period import Period
from wetterdienst.model.request import TimeseriesRequest
from wetterdienst.model.result import (
    InterpolatedValuesResult,
    StationsFilter,
    StationsResult,
    SummarizedValuesResult,
    ValuesResult,
)
from wetterdienst.model.util import filter_by_date
from wetterdienst.model.values import TimeseriesValues
from wetterdienst.provider.dwd.observation import (
    DwdObservationRequest,
)


@pytest.fixture
def dwd_climate_summary_tabular_columns() -> list[str]:
    """Provide tabular columns for climate summary."""
    return [
        "station_id",
        "resolution",
        "dataset",
        "timestamp",
        "wind_gust_max",
        "wind_gust_max_quality",
        "wind_speed",
        "wind_speed_quality",
        "precipitation_amount",
        "precipitation_amount_quality",
        "precipitation_form",
        "precipitation_form_quality",
        "sunshine_duration",
        "sunshine_duration_quality",
        "snow_depth",
        "snow_depth_quality",
        "cloud_cover_total",
        "cloud_cover_total_quality",
        "pressure_vapor",
        "pressure_vapor_quality",
        "pressure_air_site",
        "pressure_air_site_quality",
        "temperature_air_mean_2m",
        "temperature_air_mean_2m_quality",
        "humidity_relative",
        "humidity_relative_quality",
        "temperature_air_max_2m",
        "temperature_air_max_2m_quality",
        "temperature_air_min_2m",
        "temperature_air_min_2m_quality",
        "temperature_air_min_0_05m",
        "temperature_air_min_0_05m_quality",
    ]


@pytest.fixture
def df_stations() -> pl.DataFrame:
    """Provide DataFrame of stations."""
    return pl.DataFrame(
        [
            {
                "resolution": "daily",
                "dataset": "climate_summary",
                "station_id": "01048",
                "start_date": dt.datetime(1957, 5, 1, tzinfo=ZoneInfo("UTC")),
                "end_date": dt.datetime(1995, 11, 30, tzinfo=ZoneInfo("UTC")),
                "elevation": 645.0,
                "latitude": 48.8049,
                "longitude": 13.5528,
                "name": "Freyung vorm Wald",
                "region": "Bayern",
            },
        ],
        orient="row",
    )


@pytest.fixture
def stations_mock() -> TimeseriesRequest:
    """Provide Stations mock."""

    class MetadataMock:
        name_local = "Deutscher Wetterdienst"
        name_english = "German Weather Service"
        country = "Germany"
        copyright = "© Deutscher Wetterdienst (DWD), Climate Data Center (CDC)"
        url = "https://opendata.dwd.de/climate_environment/CDC/"

    class StationsMock:
        metadata = MetadataMock

    return StationsMock


@pytest.fixture
def stations_result_mock(df_stations: pl.DataFrame, stations_mock: TimeseriesRequest) -> StationsResult:
    """Provide StationsResult mock."""
    return StationsResult(
        df=df_stations,
        df_all=df_stations,
        stations_filter=StationsFilter.ALL,
        stations=stations_mock,
    )


@pytest.fixture
def df_values() -> pl.DataFrame:
    """Provide DataFrame of values."""
    return pl.DataFrame(
        [
            {
                "station_id": "01048",
                "resolution": "daily",
                "dataset": "climate_summary",
                "parameter": "temperature_air_max_2m",
                "timestamp": dt.datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC")),
                "value": 1.3,
                "quality": None,
            },
            {
                "station_id": "01048",
                "resolution": "daily",
                "dataset": "climate_summary",
                "parameter": "temperature_air_max_2m",
                "timestamp": dt.datetime(2019, 12, 1, tzinfo=ZoneInfo("UTC")),
                "value": 1.0,
                "quality": None,
            },
            {
                "station_id": "01048",
                "resolution": "daily",
                "dataset": "climate_summary",
                "parameter": "temperature_air_max_2m",
                "timestamp": dt.datetime(2019, 12, 28, tzinfo=ZoneInfo("UTC")),
                "value": 1.3,
                "quality": None,
            },
            {
                "station_id": "01048",
                "resolution": "daily",
                "dataset": "climate_summary",
                "parameter": "temperature_air_max_2m",
                "timestamp": dt.datetime(2020, 1, 1, tzinfo=ZoneInfo("UTC")),
                "value": 2.0,
                "quality": None,
            },
            {
                "station_id": "01048",
                "resolution": "daily",
                "dataset": "climate_summary",
                "parameter": "temperature_air_max_2m",
                "timestamp": dt.datetime(2021, 1, 1, tzinfo=ZoneInfo("UTC")),
                "value": 3.0,
                "quality": None,
            },
            {
                "station_id": "01048",
                "resolution": "daily",
                "dataset": "climate_summary",
                "parameter": "temperature_air_max_2m",
                "timestamp": dt.datetime(2022, 1, 1, tzinfo=ZoneInfo("UTC")),
                "value": 4.0,
                "quality": None,
            },
        ],
        schema={
            "station_id": pl.String,
            "resolution": pl.String,
            "dataset": pl.String,
            "parameter": pl.String,
            "timestamp": pl.Datetime(time_zone="UTC"),
            "value": pl.Float64,
            "quality": pl.Float64,
        },
        orient="row",
    )


@pytest.fixture
def df_interpolated_values() -> pl.DataFrame:
    """Provide DataFrame of interpolated values."""
    return pl.DataFrame(
        [
            {
                "station_id": "abc",
                "resolution": "daily",
                "dataset": "climate_summary",
                "parameter": "temperature_air_max_2m",
                "timestamp": dt.datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC")),
                "value": 1.3,
                "distance_mean": 5.3,
                "taken_station_ids": ["01048", "1050"],
            },
        ],
        schema={
            "station_id": pl.String,
            "resolution": pl.String,
            "dataset": pl.String,
            "parameter": pl.String,
            "timestamp": pl.Datetime(time_zone="UTC"),
            "value": pl.Float64,
            "distance_mean": pl.Float64,
            "taken_station_ids": pl.List(pl.String),
        },
        orient="row",
    )


@pytest.fixture
def df_summarized_values() -> pl.DataFrame:
    """Provide summarized values."""
    return pl.DataFrame(
        [
            {
                "station_id": "abc",
                "resolution": "daily",
                "dataset": "climate_summary",
                "parameter": "temperature_air_max_2m",
                "timestamp": dt.datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC")),
                "value": 1.3,
                "distance": 0.0,
                "taken_station_id": "01048",
            },
        ],
        schema={
            "station_id": pl.String,
            "resolution": pl.String,
            "dataset": pl.String,
            "parameter": pl.String,
            "timestamp": pl.Datetime(time_zone="UTC"),
            "value": pl.Float64,
            "distance": pl.Float64,
            "taken_station_id": pl.String,
        },
        orient="row",
    )


def test_stations_to_dict(df_stations: pl.DataFrame) -> None:
    """Test export of DataFrame of stations to dictionary."""
    data = StationsResult(
        df=df_stations,
        df_all=df_stations,
        stations_filter=StationsFilter.ALL,
        stations=None,
    ).to_dict()
    assert data.keys() == {"stations"}
    assert data["stations"] == [
        {
            "resolution": "daily",
            "dataset": "climate_summary",
            "station_id": "01048",
            "start_date": "1957-05-01T00:00:00.000000+00:00",
            "end_date": "1995-11-30T00:00:00.000000+00:00",
            "elevation": 645.0,
            "latitude": 48.8049,
            "longitude": 13.5528,
            "name": "Freyung vorm Wald",
            "region": "Bayern",
        },
    ]


def test_stations_to_dict_with_metadata(
    df_stations: pl.DataFrame,
    stations_mock: TimeseriesRequest,
    metadata: dict,
) -> None:
    """Test export of DataFrame of stations to dictionary with metadata."""
    data = StationsResult(
        df=df_stations,
        df_all=df_stations,
        stations_filter=StationsFilter.ALL,
        stations=stations_mock,
    ).to_dict(with_metadata=True)
    assert data.keys() == {"stations", "metadata"}
    assert data["metadata"] == metadata


def test_stations_to_ogc_feature_collection(df_stations: pl.DataFrame) -> None:
    """Test export of DataFrame of stations to OGC feature collection."""
    data = StationsResult(
        df=df_stations,
        df_all=df_stations,
        stations_filter=StationsFilter.ALL,
        stations=None,
    ).to_ogc_feature_collection()
    assert data.keys() == {"data"}
    assert data["data"]["features"][0] == {
        "geometry": {"coordinates": [13.5528, 48.8049, 645.0], "type": "Point"},
        "properties": {
            "resolution": "daily",
            "dataset": "climate_summary",
            "id": "01048",
            "start_date": "1957-05-01T00:00:00.000000+00:00",
            "end_date": "1995-11-30T00:00:00.000000+00:00",
            "name": "Freyung vorm Wald",
            "region": "Bayern",
        },
        "type": "Feature",
    }


def test_stations_to_ogc_feature_collection_with_metadata(
    df_stations: pl.DataFrame,
    stations_mock: TimeseriesRequest,
    metadata: dict,
) -> None:
    """Test export of DataFrame of stations to OGC feature collection with metadata."""
    data = StationsResult(
        df=df_stations,
        df_all=df_stations,
        stations_filter=StationsFilter.ALL,
        stations=stations_mock,
    ).to_ogc_feature_collection(with_metadata=True)
    assert data.keys() == {"data", "metadata"}
    assert data["metadata"] == metadata


def test_stations_format_json(df_stations: pl.DataFrame) -> None:
    """Test export of DataFrame to json."""
    output = StationsResult(
        df=df_stations,
        df_all=df_stations,
        stations_filter=StationsFilter.ALL,
        stations=None,
    ).to_json()
    response = json.loads(output)
    assert response.keys() == {"stations"}
    station_ids = {station["station_id"] for station in response["stations"]}
    assert "01048" in station_ids


def test_stations_format_geojson(df_stations: pl.DataFrame, stations_mock: TimeseriesRequest) -> None:
    """Test export of DataFrame to geojson."""
    output = StationsResult(
        df=df_stations,
        df_all=df_stations,
        stations_filter=StationsFilter.ALL,
        stations=stations_mock,
    ).to_geojson()
    response = json.loads(output)
    assert response.keys() == {"data"}
    station_names = {station["properties"]["name"] for station in response["data"]["features"]}
    assert "Freyung vorm Wald" in station_names


def test_stations_format_csv(df_stations: pl.DataFrame) -> None:
    """Test export of DataFrame to csv."""
    output = (
        StationsResult(
            df=df_stations,
            df_all=df_stations,
            stations_filter=StationsFilter.ALL,
            stations=None,
        )
        .to_csv()
        .strip()
    )
    lines = output.split("\n")
    assert lines[0] == "resolution,dataset,station_id,start_date,end_date,elevation,latitude,longitude,name,region"
    assert (
        lines[1] == "daily,climate_summary,01048,1957-05-01T00:00:00.000000+00:00,1995-11-30T00:00:00.000000+00:00,"
        "645.0,48.8049,13.5528,Freyung vorm Wald,Bayern"
    )


def test_values_to_dict(df_values: pl.DataFrame) -> None:
    """Test export of DataFrame of values to dictionary."""
    data = ValuesResult(stations=None, values=None, df=df_values[0, :]).to_dict()
    assert data.keys() == {"values"}
    assert data["values"] == [
        {
            "station_id": "01048",
            "resolution": "daily",
            "dataset": "climate_summary",
            "parameter": "temperature_air_max_2m",
            "timestamp": "2019-01-01T00:00:00.000000+00:00",
            "value": 1.3,
            "quality": None,
        },
    ]


def test_values_to_dict_with_metadata(
    df_values: pl.DataFrame,
    stations_result_mock: StationsResult,
    metadata: dict,
) -> None:
    """Test export of DataFrame of values to dictionary with metadata."""
    data = ValuesResult(stations=stations_result_mock, values=None, df=df_values[0, :]).to_dict(with_metadata=True)
    assert data.keys() == {"values", "metadata"}
    assert data["metadata"] == metadata


def test_values_to_ogc_feature_collection(df_values: pl.DataFrame, stations_result_mock: StationsResult) -> None:
    """Test export of DataFrame of values to OGC feature collection."""
    # mirror the real all() output where metadata columns (incl. station_id) are Enum, to exercise
    # the stations<->values join in to_ogc_feature_collection (regression test for an Enum/String mismatch)
    df_values = TimeseriesValues._cast_metadata_to_enum(df_values)  # noqa: SLF001
    data = ValuesResult(stations=stations_result_mock, values=None, df=df_values[0, :]).to_ogc_feature_collection()
    assert data.keys() == {"data"}
    assert data["data"]["features"][0] == {
        "geometry": {"coordinates": [13.5528, 48.8049, 645.0], "type": "Point"},
        "properties": {
            "resolution": "daily",
            "dataset": "climate_summary",
            "id": "01048",
            "name": "Freyung vorm Wald",
            "region": "Bayern",
            "start_date": "1957-05-01T00:00:00.000000+00:00",
            "end_date": "1995-11-30T00:00:00.000000+00:00",
        },
        "type": "Feature",
        "values": [
            {
                "resolution": "daily",
                "dataset": "climate_summary",
                "parameter": "temperature_air_max_2m",
                "timestamp": "2019-01-01T00:00:00.000000+00:00",
                "value": 1.3,
                "quality": None,
            },
        ],
    }


def test_values_to_ogc_feature_collection_with_metadata(
    df_values: pl.DataFrame,
    stations_result_mock: StationsResult,
    metadata: dict,
) -> None:
    """Test export of DataFrame of values to OGC feature collection with metadata."""
    df_values = TimeseriesValues._cast_metadata_to_enum(df_values)  # noqa: SLF001
    data = ValuesResult(stations=stations_result_mock, values=None, df=df_values[0, :]).to_ogc_feature_collection(
        with_metadata=True,
    )
    assert data.keys() == {"data", "metadata"}
    assert data["metadata"] == metadata


def test_values_format_json(df_values: pl.DataFrame) -> None:
    """Test export of DataFrame to json."""
    output = ValuesResult(stations=None, values=None, df=df_values).to_json()
    response = json.loads(output)
    assert response.keys() == {"values"}
    station_ids = {reading["station_id"] for reading in response["values"]}
    assert "01048" in station_ids


def test_values_format_geojson(df_values: pl.DataFrame, stations_result_mock: StationsResult) -> None:
    """Test export of DataFrame to geojson."""
    output = ValuesResult(df=df_values, stations=stations_result_mock, values=None).to_geojson()
    response = json.loads(output)
    assert response.keys() == {"data"}
    item = response["data"]["features"][0]["values"][0]
    assert item == {
        "resolution": "daily",
        "dataset": "climate_summary",
        "parameter": "temperature_air_max_2m",
        "timestamp": "2019-01-01T00:00:00.000000+00:00",
        "value": 1.3,
        "quality": None,
    }


def test_values_format_csv(df_values: pl.DataFrame) -> None:
    """Test export of DataFrame to csv."""
    output = ValuesResult(stations=None, values=None, df=df_values).to_csv().strip()
    lines = output.split("\n")
    assert lines[0] == "station_id,resolution,dataset,parameter,timestamp,value,quality"
    assert lines[-1] == "01048,daily,climate_summary,temperature_air_max_2m,2022-01-01T00:00:00.000000+00:00,4.0,"


def test_values_format_csv_kwargs(df_values: pl.DataFrame) -> None:
    """Test export of DataFrame to csv."""
    output = ValuesResult(stations=None, values=None, df=df_values).to_csv(include_header=False).strip()
    lines = output.split("\n")
    assert lines[0] == "01048,daily,climate_summary,temperature_air_max_2m,2019-01-01T00:00:00.000000+00:00,1.3,"


def test_interpolated_values_to_dict(df_interpolated_values: pl.DataFrame) -> None:
    """Test export of DataFrame of interpolated values to dictionary."""
    data = InterpolatedValuesResult(stations=None, df=df_interpolated_values, latlon=(1, 2)).to_dict()
    assert data.keys() == {"values"}
    assert data["values"] == [
        {
            "station_id": "abc",
            "resolution": "daily",
            "dataset": "climate_summary",
            "parameter": "temperature_air_max_2m",
            "timestamp": "2019-01-01T00:00:00.000000+00:00",
            "value": 1.3,
            "distance_mean": 5.3,
            "taken_station_ids": ["01048", "1050"],
        },
    ]


def test_interpolated_values_to_csv(df_interpolated_values: pl.DataFrame) -> None:
    """Test export of DataFrame of interpolated values to dictionary."""
    output = InterpolatedValuesResult(stations=None, df=df_interpolated_values, latlon=(1, 2)).to_csv(
        include_header=False
    )
    lines = output.split("\n")
    assert (
        lines[0]
        == 'abc,daily,climate_summary,temperature_air_max_2m,2019-01-01T00:00:00.000000+00:00,1.3,5.3,"01048,1050"'
    )


def test_interpolated_values_to_dict_with_metadata(
    df_interpolated_values: pl.DataFrame,
    stations_result_mock: StationsResult,
    metadata: dict,
) -> None:
    """Test export of DataFrame of interpolated values to dictionary with metadata."""
    data = InterpolatedValuesResult(stations=stations_result_mock, df=df_interpolated_values, latlon=(1, 2)).to_dict(
        with_metadata=True,
    )
    assert data.keys() == {"values", "metadata"}
    assert data["metadata"] == metadata


def test_interpolated_values_to_ogc_feature_collection(
    df_interpolated_values: pl.DataFrame,
    stations_result_mock: StationsResult,
) -> None:
    """Test export of DataFrame of interpolated values to OGC feature collection."""
    data = InterpolatedValuesResult(
        stations=stations_result_mock,
        df=df_interpolated_values,
        latlon=(1.2345, 2.3456),
    ).to_ogc_feature_collection()
    assert data.keys() == {"data"}
    assert data["data"]["features"][0] == {
        "geometry": {"coordinates": [2.3456, 1.2345], "type": "Point"},
        # the id is the name hashed, as the interpolation itself builds it -- not read out of the
        # frame, whose station_id is a placeholder here
        "properties": {"id": "ea536c83", "name": "interpolation(1.2345,2.3456)"},
        "stations": [
            {
                "resolution": "daily",
                "dataset": "climate_summary",
                "station_id": "01048",
                "start_date": "1957-05-01T00:00:00.000000+00:00",
                "end_date": "1995-11-30T00:00:00.000000+00:00",
                "latitude": 48.8049,
                "longitude": 13.5528,
                "elevation": 645.0,
                "name": "Freyung vorm Wald",
                "region": "Bayern",
            },
        ],
        "type": "Feature",
        "values": [
            {
                "station_id": "abc",
                "resolution": "daily",
                "dataset": "climate_summary",
                "parameter": "temperature_air_max_2m",
                "timestamp": "2019-01-01T00:00:00.000000+00:00",
                "value": 1.3,
                "distance_mean": 5.3,
                "taken_station_ids": ["01048", "1050"],
            },
        ],
    }


def test_interpolated_values_to_ogc_feature_collection_with_metadata(
    df_interpolated_values: pl.DataFrame,
    stations_result_mock: StationsResult,
    metadata: dict,
) -> None:
    """Test export of DataFrame of interpolated values to OGC feature collection with metadata."""
    data = InterpolatedValuesResult(
        stations=stations_result_mock,
        df=df_interpolated_values,
        latlon=(1.2345, 2.3456),
    ).to_ogc_feature_collection(with_metadata=True)
    assert data.keys() == {"data", "metadata"}
    assert data["metadata"] == metadata


def test_summarized_values_to_dict(df_summarized_values: pl.DataFrame) -> None:
    """Test export of DataFrame of summarized values to dictionary."""
    data = SummarizedValuesResult(stations=None, df=df_summarized_values, latlon=(1.2345, 2.3456)).to_dict()
    assert data.keys() == {"values"}
    assert data["values"] == [
        {
            "station_id": "abc",
            "resolution": "daily",
            "dataset": "climate_summary",
            "parameter": "temperature_air_max_2m",
            "timestamp": "2019-01-01T00:00:00.000000+00:00",
            "value": 1.3,
            "distance": 0.0,
            "taken_station_id": "01048",
        },
    ]


def test_summarized_values_to_csv(df_summarized_values: pl.DataFrame) -> None:
    """Test export of DataFrame of summarized values to csv."""
    output = SummarizedValuesResult(stations=None, df=df_summarized_values, latlon=(1.2345, 2.3456)).to_csv(
        include_header=False
    )
    lines = output.split("\n")
    assert lines[0] == "abc,daily,climate_summary,temperature_air_max_2m,2019-01-01T00:00:00.000000+00:00,1.3,0.0,01048"


def test_summarized_values_to_dict_with_metadata(
    df_summarized_values: pl.DataFrame,
    stations_result_mock: StationsResult,
    metadata: dict,
) -> None:
    """Test export of DataFrame of summarized values to dictionary with metadata."""
    data = SummarizedValuesResult(
        stations=stations_result_mock,
        df=df_summarized_values,
        latlon=(1.2345, 2.3456),
    ).to_dict(with_metadata=True)
    assert data.keys() == {"values", "metadata"}
    assert data["metadata"] == metadata


def test_summarized_values_to_ogc_feature_collection(
    df_summarized_values: pl.DataFrame,
    stations_result_mock: StationsResult,
) -> None:
    """Test export of DataFrame of summarized values to OGC feature collection."""
    data = SummarizedValuesResult(
        stations=stations_result_mock,
        df=df_summarized_values,
        latlon=(1.2345, 2.3456),
    ).to_ogc_feature_collection()
    assert data.keys() == {"data"}
    assert data["data"]["features"][0] == {
        "geometry": {"coordinates": [2.3456, 1.2345], "type": "Point"},
        "properties": {"id": "875cac86", "name": "summary(1.2345,2.3456)"},
        "stations": [
            {
                "resolution": "daily",
                "dataset": "climate_summary",
                "station_id": "01048",
                "start_date": "1957-05-01T00:00:00.000000+00:00",
                "end_date": "1995-11-30T00:00:00.000000+00:00",
                "latitude": 48.8049,
                "longitude": 13.5528,
                "elevation": 645.0,
                "name": "Freyung vorm Wald",
                "region": "Bayern",
            },
        ],
        "type": "Feature",
        "values": [
            {
                "station_id": "abc",
                "resolution": "daily",
                "dataset": "climate_summary",
                "parameter": "temperature_air_max_2m",
                "timestamp": "2019-01-01T00:00:00.000000+00:00",
                "value": 1.3,
                "distance": 0.0,
                "taken_station_id": "01048",
            },
        ],
    }


def test_summarized_values_to_ogc_feature_collection_with_metadata(
    df_summarized_values: pl.DataFrame,
    stations_result_mock: StationsResult,
    metadata: dict,
) -> None:
    """Test export of DataFrame of summarized values to OGC feature collection with metadata."""
    data = SummarizedValuesResult(
        stations=stations_result_mock,
        df=df_summarized_values,
        latlon=(1.2345, 2.3456),
    ).to_ogc_feature_collection(with_metadata=True)
    assert data.keys() == {"data", "metadata"}
    assert data["metadata"] == metadata


def test_filter_by_date(df_values: pl.DataFrame) -> None:
    """Test filter by date."""
    df = filter_by_date(df_values, "2019-12-28")
    assert not df.is_empty()
    df = filter_by_date(df_values, "2019-12-27")
    assert df.is_empty()


def test_filter_by_date_interval(df_values: pl.DataFrame) -> None:
    """Test filter by date interval."""
    df = filter_by_date(df_values, "2019-12-27/2019-12-29")
    assert not df.is_empty()
    df = filter_by_date(df_values, "2019-12/2020-01")
    assert df.get_column("value").to_list() == [1.0, 1.3, 2.0]
    df = filter_by_date(df, date="2020/2022")
    assert not df.is_empty()
    df = filter_by_date(df, date="2020")
    assert not df.is_empty()


@pytest.mark.parametrize(
    ("result_class", "name", "expected_id"),
    [
        (InterpolatedValuesResult, "interpolation(1.2345,2.3456)", "ea536c83"),
        (SummarizedValuesResult, "summary(1.2345,2.3456)", "875cac86"),
    ],
)
def test_interpolated_or_summarized_ogc_feature_collection_without_values(
    result_class: type,
    name: str,
    expected_id: str,
    df_interpolated_values: pl.DataFrame,
    df_summarized_values: pl.DataFrame,
    stations_result_mock: StationsResult,
) -> None:
    """A result that came back with no rows is a feature collection with no values.

    The feature's id was read out of the frame, so an interpolation or summary over a window no
    station covers -- an ordinary outcome, and one the REST API serves as `format=geojson` --
    raised `OutOfBoundsError: gather indices are out of bounds` instead of answering. The id
    belongs to the point rather than to any row, and is the name beside it hashed.
    """
    df = df_interpolated_values if result_class is InterpolatedValuesResult else df_summarized_values
    data = result_class(
        stations=stations_result_mock, df=df.clear(), latlon=(1.2345, 2.3456)
    ).to_ogc_feature_collection()
    feature = data["data"]["features"][0]
    assert feature["properties"] == {"id": expected_id, "name": name}
    assert feature["values"] == []


@pytest.mark.parametrize(
    ("settings_kwargs", "parameter_in_frame", "expected"),
    [
        ({}, "sunshine_duration", "sunshine_duration (s)"),
        ({"ts_humanize": False}, "sd_10", "sd_10 (s)"),
        ({"ts_convert_units": False}, "sunshine_duration", "sunshine_duration (h)"),
        ({"ts_humanize": False, "ts_convert_units": False}, "sd_10", "sd_10 (h)"),
    ],
)
def test_values_plot_labels_the_unit_the_values_carry(
    settings_kwargs: dict,
    parameter_in_frame: str,
    expected: str,
) -> None:
    """A plot labels a parameter with the unit its values are actually written in.

    Two ways that went wrong. The label mapping was keyed on the canonical parameter name alone,
    while a frame carries `name_original` unless `ts_humanize` is on, so nothing matched and the
    label repeated the name: `sd_10 (sd_10)`. And the symbol was always the target unit's, though
    `ts_convert_units=False` leaves the values as the source published them -- sunshine duration
    comes in hours and was labelled seconds, a factor of 3600 between the number and its unit.
    """
    request = DwdObservationRequest(
        parameters=["10_minutes/solar/sunshine_duration"],
        settings=Settings(**settings_kwargs),
    )
    stations = StationsResult(
        stations=request,
        df=pl.DataFrame(),
        df_all=pl.DataFrame(),
        stations_filter=StationsFilter.ALL,
    )
    df = pl.DataFrame(
        {
            "station_id": ["01048"],
            "resolution": ["10_minutes"],
            "dataset": ["solar"],
            "parameter": [parameter_in_frame],
            "timestamp": [dt.datetime(2020, 1, 1, tzinfo=ZoneInfo("UTC"))],
            "value": [1.0],
        },
    )
    pytest.importorskip("plotly")
    figure = ValuesResult(stations=stations, values=stations.values, df=df).to_plot()
    assert [annotation.text for annotation in figure.layout.annotations] == [expected]


def test_values_plot_labels_one_name_published_in_two_units() -> None:
    """A canonical name is only unique within its dataset, and the label follows the dataset.

    DWD publishes `sunshine_duration` in hours at 10 minutes and in minutes at an hour. Keyed on
    the name alone, one of them labelled the other -- and left unconverted, that is a factor of 60
    between the number and its unit.
    """
    pytest.importorskip("plotly")
    request = DwdObservationRequest(
        parameters=["10_minutes/solar/sunshine_duration", "hourly/sun/sunshine_duration"],
        settings=Settings(ts_convert_units=False),
    )
    stations = StationsResult(
        stations=request,
        df=pl.DataFrame(),
        df_all=pl.DataFrame(),
        stations_filter=StationsFilter.ALL,
    )
    df = pl.DataFrame(
        {
            "station_id": ["01048", "01048"],
            "resolution": ["10_minutes", "hourly"],
            "dataset": ["solar", "sun"],
            "parameter": ["sunshine_duration", "sunshine_duration"],
            "timestamp": [dt.datetime(2020, 1, 1, tzinfo=ZoneInfo("UTC"))] * 2,
            "value": [1.0, 2.0],
        },
    )
    figure = ValuesResult(stations=stations, values=stations.values, df=df).to_plot()
    assert sorted(annotation.text for annotation in figure.layout.annotations) == [
        "10_minutes<br>solar<br>sunshine_duration (h)",
        "hourly<br>sun<br>sunshine_duration (min)",
    ]


@pytest.fixture
def df_hourly_values() -> pl.DataFrame:
    """Provide an hourly DataFrame, where a day is 24 readings rather than one."""
    return pl.DataFrame(
        {
            "timestamp": [dt.datetime(2019, 12, 28, hour, tzinfo=ZoneInfo("UTC")) for hour in range(24)]
            + [dt.datetime(2019, 12, 15, tzinfo=ZoneInfo("UTC")), dt.datetime(2020, 1, 15, tzinfo=ZoneInfo("UTC"))],
            "value": [float(hour) for hour in range(24)] + [99.0, 111.0],
        },
        schema={"timestamp": pl.Datetime(time_zone="UTC"), "value": pl.Float64},
    )


def test_filter_by_date_covers_the_span_the_string_names(df_hourly_values: pl.DataFrame) -> None:
    """A date string keeps everything measured within what it names, not just its first instant.

    Every one of these formats is documented as supported, and each was read as the instant it
    starts with: a day of hourly readings came back as the one at midnight, and a month or a year
    of them as nothing at all, because no reading falls exactly on the 1st of the month at 00:00.
    """
    assert filter_by_date(df_hourly_values, "2019-12-28").height == 24
    assert filter_by_date(df_hourly_values, "2019-12").height == 25
    assert filter_by_date(df_hourly_values, "2019").height == 25
    # a date carrying a time still names one instant
    assert filter_by_date(df_hourly_values, "2019-12-28T05").height == 1
    assert filter_by_date(df_hourly_values, "2019-12-27").is_empty()


def test_filter_by_date_interval_ends_with_the_span_it_names(df_hourly_values: pl.DataFrame) -> None:
    """An interval runs to the end of the span its second half names, not to its first instant.

    "2019-12/2020-01" used to end at the 1st of January at 00:00, dropping the rest of the month
    it names -- the 15th here.
    """
    assert filter_by_date(df_hourly_values, "2019-12/2020-01").height == 26
    assert filter_by_date(df_hourly_values, "2019/2020").height == 26
    # the day before the hourly readings start is still excluded from both ends
    assert filter_by_date(df_hourly_values, "2019-12-16/2019-12-27").is_empty()


def test_create_date_range_covers_the_span_the_string_names() -> None:
    """The date range covers what the string names, and a coarse resolution widens it further.

    It sits beside `filter_by_date` and read a date the way `filter_by_date` used to, so
    "2020-05" came back as a range of one instant.
    """
    from wetterdienst.metadata.resolution import Resolution  # noqa: PLC0415
    from wetterdienst.model.util import create_date_range  # noqa: PLC0415

    utc = ZoneInfo("UTC")
    date_from, date_to = create_date_range("2020-05", Resolution.HOURLY)
    assert date_from == dt.datetime(2020, 5, 1, tzinfo=utc)
    assert date_to == dt.datetime(2020, 6, 1, tzinfo=utc) - dt.timedelta(microseconds=1)
    # a monthly resolution still widens a day to the month holding it
    assert create_date_range("2020-05-15", Resolution.MONTHLY) == (
        dt.datetime(2020, 5, 1, tzinfo=utc),
        dt.datetime(2020, 5, 31, tzinfo=utc),
    )


@pytest.mark.sql
def test_filter_by_sql_on_stations(df_stations: pl.DataFrame) -> None:
    """Station metadata can be filtered by SQL through a result.

    `ExportMixin.filter_by_sql` stripped the time zone off a `date` column, which a stations frame
    does not have -- it carries `start_date` and `end_date` -- so `request.all().filter_by_sql(...)`
    raised `ColumnNotFoundError`. The CLI's own `--sql` goes through `TimeseriesRequest`, which
    named those two columns itself and so worked; both run this one filter now.
    """
    df = ExportMixin(df=df_stations).filter_by_sql("region='Bayern'")
    assert df.get_column("station_id").to_list() == ["01048"]
    # the timestamps keep the zone they came with
    assert df.schema["start_date"].time_zone == "UTC"
    assert ExportMixin(df=df_stations).filter_by_sql("region='Sachsen'").is_empty()


@pytest.mark.sql
def test_filter_by_sql_names_a_renamed_column(df_stations: pl.DataFrame, df_values: pl.DataFrame) -> None:
    """A filter on a column renamed for 1.0 says what the column is called now (GH-2024, GH-2026, GH-2028)."""
    import duckdb  # noqa: PLC0415

    with pytest.raises(duckdb.BinderException, match='column "date" was renamed to "timestamp"'):
        ExportMixin(df=df_values).filter_by_sql("date >= '2019-01-01'")
    # a stations frame never had `date` and has no `timestamp` to be sent to either
    with pytest.raises(duckdb.BinderException, match='Referenced column "date" not found'):
        ExportMixin(df=df_stations).filter_by_sql("date >= '2019-01-01'")

    with pytest.raises(duckdb.BinderException, match='column "height" was renamed to "elevation"'):
        ExportMixin(df=df_stations).filter_by_sql("height > 500")
    # DuckDB matches identifiers regardless of case, and so does the hint
    with pytest.raises(duckdb.BinderException, match='column "HEIGHT" was renamed to "elevation"'):
        ExportMixin(df=df_stations).filter_by_sql("HEIGHT > 500")
    # qualified by the table, which DuckDB reports in other words
    with pytest.raises(duckdb.BinderException, match='column "height" was renamed to "elevation"'):
        ExportMixin(df=df_stations).filter_by_sql("df.height > 500")
    # a values frame never had `height`, nor has it `elevation`, so DuckDB's own error stands
    with pytest.raises(duckdb.BinderException, match='Referenced column "height" not found'):
        ExportMixin(df=df_values).filter_by_sql("height > 500")
    with pytest.raises(duckdb.BinderException, match='column "state" was renamed to "region"'):
        ExportMixin(df=df_stations).filter_by_sql("state = 'Bayern'")
    # a column that never existed keeps DuckDB's own error
    with pytest.raises(duckdb.BinderException, match='Referenced column "altitude" not found'):
        ExportMixin(df=df_stations).filter_by_sql("altitude > 500")
    assert ExportMixin(df=df_stations).filter_by_sql("elevation > 500").get_column("station_id").to_list() == ["01048"]


@pytest.mark.sql
def test_filter_by_sql_names_a_renamed_wide_quality_column() -> None:
    """A wide frame's `qn_<parameter>` is named by the column it is now (GH-2030)."""
    import duckdb  # noqa: PLC0415

    df = pl.DataFrame({"temperature_air_mean_2m": [1.5], "temperature_air_mean_2m_quality": [10.0]})
    with pytest.raises(
        duckdb.BinderException,
        match='column "qn_temperature_air_mean_2m" was renamed to "temperature_air_mean_2m_quality"',
    ):
        ExportMixin(df=df).filter_by_sql("qn_temperature_air_mean_2m = 10")
    # DuckDB matches identifiers regardless of case, and so does the hint
    with pytest.raises(duckdb.BinderException, match='was renamed to "temperature_air_mean_2m_quality"'):
        ExportMixin(df=df).filter_by_sql("QN_Temperature_Air_Mean_2m = 10")
    # a frame whose columns carry case, as source names do with humanize off, is named in its own
    df = pl.DataFrame({"TMK": [1.5], "TMK_quality": [10.0]})
    with pytest.raises(duckdb.BinderException, match='column "qn_tmk" was renamed to "TMK_quality"'):
        ExportMixin(df=df).filter_by_sql("qn_tmk = 10")
    # a `qn_` column whose successor the frame does not hold is simply not there
    with pytest.raises(duckdb.BinderException, match='Referenced column "qn_wind_speed" not found'):
        ExportMixin(df=df).filter_by_sql("qn_wind_speed = 10")


@pytest.mark.sql
def test_filter_by_sql_names_a_renamed_parameter_column() -> None:
    """A wide frame's column after a renamed parameter, and its quality column, name the new ones (GH-2032)."""
    import duckdb  # noqa: PLC0415

    df = pl.DataFrame({"wave_height_significant": [1.5], "wave_height_significant_quality": [10.0]})
    for old in ("wave_height_sign", "wave_height_sign_quality", "qn_wave_height_sign"):
        new = "wave_height_significant" if old == "wave_height_sign" else "wave_height_significant_quality"
        with pytest.raises(duckdb.BinderException, match=f'column "{old}" was renamed to "{new}"'):
            ExportMixin(df=df).filter_by_sql(f"{old} > 1")
    # several datasets prefix each column with its dataset, and the rename follows the parameter
    df = pl.DataFrame({"soil_thawing_thickness_bare_ground": [3.0]})
    with pytest.raises(
        duckdb.BinderException,
        match='column "soil_thawing_thickness_bare" was renamed to "soil_thawing_thickness_bare_ground"',
    ):
        ExportMixin(df=df).filter_by_sql("soil_thawing_thickness_bare > 1")


@pytest.mark.sql
def test_filter_by_sql_keeps_duckdbs_error_for_a_column_that_was_not_renamed() -> None:
    """A column the frame has, missing only where the query looks for it, gets DuckDB's own error.

    So does a name that only looks renamed: a current parameter ending in a renamed name's
    successor is no dataset prefix, so its `_24h` variant was never a column of any frame.
    """
    import duckdb  # noqa: PLC0415

    df = pl.DataFrame({"station_id": ["01048"], "value": [1.0]})
    with pytest.raises(duckdb.BinderException, match='Referenced column "value" not found') as error:
        ExportMixin(df=df).filter_by_sql("true UNION ALL SELECT * FROM (SELECT 'b' s) WHERE value > 0")
    assert "renamed" not in str(error.value)
    df = pl.DataFrame({"count_days_multiday_wind_movement": [2.0]})
    with pytest.raises(duckdb.BinderException, match='Referenced column "count_days_multiday_wind_movement_24h"'):
        ExportMixin(df=df).filter_by_sql("count_days_multiday_wind_movement_24h > 0")


@pytest.mark.parametrize("extension", ["csv", "json", "jsonl", "xlsx", "parquet", "feather"])
def test_export_file_targets_take_a_stations_frame(
    df_stations: pl.DataFrame,
    tmp_path: Path,
    extension: str,
) -> None:
    """Every flat file target takes a frame without a `timestamp` column."""
    filename = tmp_path.joinpath(f"stations.{extension}")
    ExportMixin(df=df_stations).to_target(f"file://{filename}")
    assert filename.exists()


def test_export_csv_file_matches_to_csv(df_interpolated_values: pl.DataFrame, tmp_path: Path) -> None:
    """The CSV a file target writes is the CSV `to_csv` returns.

    `taken_station_ids` is a list, which `to_csv` joins into one field and the file target did not,
    so `--target=file://out.csv` on an interpolation died with `CSV format does not support nested
    data` while `--format=csv` wrote it out fine.
    """
    filename = tmp_path.joinpath("values.csv")
    exporter = ExportMixin(df=df_interpolated_values)
    exporter.to_target(f"file://{filename}")
    assert filename.read_text() == exporter.to_csv()
    assert '"01048,1050"' in filename.read_text()


@pytest.mark.parametrize("extension", ["json", "jsonl"])
def test_export_json_targets(df_values: pl.DataFrame, tmp_path: Path, extension: str) -> None:
    """JSON and JSON Lines are written as the records they hold."""
    filename = tmp_path.joinpath(f"values.{extension}")
    ExportMixin(df=df_values).to_target(f"file://{filename}")
    read = pl.read_ndjson(filename) if extension == "jsonl" else pl.read_json(filename)
    assert read.height == df_values.height
    # timestamps as ISO strings, as in every other flat format
    assert read.get_column("timestamp").to_list()[0].startswith("2019-01-01T00:00:00")


def test_export_netcdf(df_interpolated_values: pl.DataFrame, tmp_path: Path) -> None:
    """NetCDF is written through xarray, with CF timestamps and the station ids as one field."""
    xarray = pytest.importorskip("xarray")
    pytest.importorskip("h5netcdf")
    filename = tmp_path.joinpath("values.nc")
    ExportMixin(df=df_interpolated_values).to_target(f"file://{filename}")
    dataset = xarray.open_dataset(filename, group="climate_summary")
    assert str(dataset["timestamp"].values[0]).startswith("2019-01-01T00:00:00")
    assert dataset["taken_station_ids"].values[0] == "01048,1050"


def test_export_netcdf_keeps_gaps_as_gaps(df_values: pl.DataFrame, tmp_path: Path) -> None:
    """A missing value is NaN in NetCDF, not a number standing in for one.

    Zarr fills gaps with -999, which a CF reader would take for a measurement -- an air temperature
    of -999 degrees, or a station 999 m below the sea.
    """
    xarray = pytest.importorskip("xarray")
    pytest.importorskip("h5netcdf")
    df = df_values.with_columns(
        pl.when(pl.col("timestamp").dt.year() == 2019).then(None).otherwise(pl.col("value")).alias("value"),
    )
    filename = tmp_path.joinpath("values.nc")
    ExportMixin(df=df).to_target(f"file://{filename}")
    values = xarray.open_dataset(filename, group="climate_summary")["value"].values
    assert math.isnan(values[0])
    assert -999 not in values


def test_export_json_keeps_a_list_a_list(df_interpolated_values: pl.DataFrame, tmp_path: Path) -> None:
    """JSON has arrays of its own, so the station ids stay a list rather than one joined field."""
    filename = tmp_path.joinpath("values.json")
    ExportMixin(df=df_interpolated_values).to_target(f"file://{filename}")
    record = json.loads(filename.read_text())[0]
    assert record["taken_station_ids"] == ["01048", "1050"]


def test_export_netcdf_without_an_engine_says_so(
    df_values: pl.DataFrame,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Without an engine xarray can write NetCDF with, the export names the extra that carries one.

    Left to xarray the failure is a ValueError listing backends, which says nothing about how to
    get one from here.
    """
    from wetterdienst.io import export  # noqa: PLC0415

    monkeypatch.setattr(export, "_netcdf_engine", lambda: None)
    with pytest.raises(ImportError, match=r"wetterdienst\[export\]"):
        ExportMixin(df=df_values).to_target(f"file://{tmp_path.joinpath('values.nc')}")


@pytest.mark.sql
def test_filter_by_sql(df_values: pl.DataFrame) -> None:
    """Test filter by sql statement."""
    df = ExportMixin(df=df_values).filter_by_sql(
        sql="parameter='temperature_air_max_2m' AND value < 1.5",
    )
    assert not df.is_empty()
    df = ExportMixin(df=df_values).filter_by_sql(
        sql="parameter='temperature_air_max_2m' AND value > 4",
    )
    assert df.is_empty()


@pytest.mark.remote
def test_request(default_settings: Settings) -> None:
    """Test general data request."""
    request = DwdObservationRequest(
        parameters=[("daily", "climate_summary")],
        periods=Period.RECENT,
        settings=default_settings,
    ).filter_by_station_id(station_id=[1048])
    df = request.values.all().df
    assert not df.is_empty()


@pytest.mark.remote
def test_export_unknown(default_settings: Settings) -> None:
    """Test export of DataFrame to unknown format."""
    request = DwdObservationRequest(
        parameters=[("daily", "climate_summary")],
        periods=Period.RECENT,
        settings=default_settings,
    ).filter_by_station_id(
        station_id=[1048],
    )
    values = request.values.all()
    with pytest.raises(ExportRefusedError) as exec_info:
        values.to_target("file:///test.foobar")
    assert exec_info.match("Unknown export file type")


@pytest.mark.remote
def test_export_excel(settings_convert_units_false_wide_shape: Settings, tmp_path: Path) -> None:
    """Test export of DataFrame to spreadsheet."""
    pytest.importorskip("fastexcel")

    # 1. Request data and save to .xlsx file.
    request = DwdObservationRequest(
        parameters=[("daily", "climate_summary")],
        start_date="2019-01-01",
        end_date="2020-01-01",
        settings=settings_convert_units_false_wide_shape,
    ).filter_by_station_id(
        station_id=[1048],
    )
    values = request.values.all()
    filename = tmp_path.joinpath("observations.xlsx")
    values.to_target(f"file://{filename}")

    # 2. Validate some details of .xlsx file.
    # Validate header row.
    df = pl.read_excel(filename)
    assert df.columns == [
        "station_id",
        "resolution",
        "dataset",
        "timestamp",
        "wind_gust_max",
        "wind_gust_max_quality",
        "wind_speed",
        "wind_speed_quality",
        "precipitation_amount",
        "precipitation_amount_quality",
        "precipitation_form",
        "precipitation_form_quality",
        "sunshine_duration",
        "sunshine_duration_quality",
        "snow_depth",
        "snow_depth_quality",
        "cloud_cover_total",
        "cloud_cover_total_quality",
        "pressure_vapor",
        "pressure_vapor_quality",
        "pressure_air_site",
        "pressure_air_site_quality",
        "temperature_air_mean_2m",
        "temperature_air_mean_2m_quality",
        "humidity_relative",
        "humidity_relative_quality",
        "temperature_air_max_2m",
        "temperature_air_max_2m_quality",
        "temperature_air_min_2m",
        "temperature_air_min_2m_quality",
        "temperature_air_min_0_05m",
        "temperature_air_min_0_05m_quality",
    ]
    # Validate number of records.
    assert len(df) == 366
    first_record = df.head(1).to_dicts()[0]
    assert first_record == {
        "station_id": "01048",
        "resolution": "daily",
        "dataset": "climate_summary",
        "timestamp": "2019-01-01T00:00:00.000000+00:00",
        "wind_gust_max": 19.9,
        "wind_gust_max_quality": 10,
        "wind_speed": 8.5,
        "wind_speed_quality": 10,
        "precipitation_amount": 0.9,
        "precipitation_amount_quality": 10,
        "precipitation_form": 8.0,
        "precipitation_form_quality": 10,
        "sunshine_duration": 0.0,
        "sunshine_duration_quality": 10,
        "snow_depth": 0,
        "snow_depth_quality": 10,
        "cloud_cover_total": 7.4,
        "cloud_cover_total_quality": 10,
        "pressure_vapor": 7.9,
        "pressure_vapor_quality": 10,
        "pressure_air_site": 991.9,
        "pressure_air_site_quality": 10,
        "temperature_air_mean_2m": 5.9,
        "temperature_air_mean_2m_quality": 10,
        "humidity_relative": 84,
        "humidity_relative_quality": 10,
        "temperature_air_max_2m": 7.5,
        "temperature_air_max_2m_quality": 10,
        "temperature_air_min_2m": 2.0,
        "temperature_air_min_2m_quality": 10,
        "temperature_air_min_0_05m": 1.5,
        "temperature_air_min_0_05m_quality": 10,
    }
    last_record = df.tail(1).to_dicts()[0]
    assert last_record == {
        "station_id": "01048",
        "resolution": "daily",
        "dataset": "climate_summary",
        "timestamp": "2020-01-01T00:00:00.000000+00:00",
        "wind_gust_max": 6.9,
        "wind_gust_max_quality": 10,
        "wind_speed": 3.2,
        "wind_speed_quality": 10,
        "precipitation_amount": 0.0,
        "precipitation_amount_quality": 10,
        "precipitation_form": 0,
        "precipitation_form_quality": 10,
        "sunshine_duration": 3.9,
        "sunshine_duration_quality": 10,
        "snow_depth": 0,
        "snow_depth_quality": 10,
        "cloud_cover_total": 4.2,
        "cloud_cover_total_quality": 10,
        "pressure_vapor": 5.7,
        "pressure_vapor_quality": 10,
        "pressure_air_site": 1005.1,
        "pressure_air_site_quality": 10,
        "temperature_air_mean_2m": 2.4,
        "temperature_air_mean_2m_quality": 10,
        "humidity_relative": 79,
        "humidity_relative_quality": 10,
        "temperature_air_max_2m": 5.6,
        "temperature_air_max_2m_quality": 10,
        "temperature_air_min_2m": -2.8,
        "temperature_air_min_2m_quality": 10,
        "temperature_air_min_0_05m": -4.6,
        "temperature_air_min_0_05m_quality": 10,
    }


@pytest.mark.remote
def test_export_parquet(
    settings_convert_units_false_wide_shape: Settings,
    dwd_climate_summary_tabular_columns: list[str],
    tmp_path: Path,
) -> None:
    """Test export of DataFrame to parquet."""
    pq = pytest.importorskip("pyarrow.parquet")
    # Request data.
    request = DwdObservationRequest(
        parameters=[("daily", "climate_summary")],
        start_date="2019-01-01",
        end_date="2020-01-01",
        settings=settings_convert_units_false_wide_shape,
    ).filter_by_station_id(
        station_id=[1048],
    )
    values = request.values.all()
    # Save to Parquet file.
    filename = tmp_path.joinpath("observation.parquet")
    values.to_target(f"file://{filename}")
    # Read back Parquet file.
    table = pq.read_table(filename)
    # Validate dimensions.
    assert table.num_columns == 32
    assert table.num_rows == 366
    # Validate column names.
    assert table.column_names == dwd_climate_summary_tabular_columns
    # Validate content.
    data = table.to_pydict()
    assert data["timestamp"][0] == dt.datetime(2019, 1, 1, 0, 0, tzinfo=ZoneInfo("UTC"))
    assert data["temperature_air_min_0_05m"][0] == 1.5
    assert data["timestamp"][-1] == dt.datetime(2020, 1, 1, 0, 0, tzinfo=ZoneInfo("UTC"))
    assert data["temperature_air_min_0_05m"][-1] == -4.6


@pytest.mark.remote
def test_export_zarr(
    settings_convert_units_false_wide_shape: Settings,
    dwd_climate_summary_tabular_columns: list[str],
    tmp_path: Path,
) -> None:
    """Test export of DataFrame to zarr."""
    zarr = pytest.importorskip("zarr")
    # Request data.
    request = DwdObservationRequest(
        parameters=[("daily", "climate_summary")],
        start_date="2019-01-01",
        end_date="2020-01-01",
        settings=settings_convert_units_false_wide_shape,
    ).filter_by_station_id(
        station_id=[1048],
    )
    values = request.values.all()
    # Save to Zarr group.
    filename = tmp_path.joinpath("observation.zarr")
    values.to_target(f"file://{filename}")

    # Read back Zarr group.
    root = zarr.open(filename, mode="r")
    group = root.get("climate_summary")
    # Validate dimensions.
    assert len(group) == 33
    assert group.get("index").size == 366
    # Validate column names.
    columns = set(group.keys())
    columns.discard("index")
    assert columns == set(dwd_climate_summary_tabular_columns)
    # Validate content.
    data = group
    assert dt.datetime.fromtimestamp(int(data["timestamp"][0]) / 1e9, tz=ZoneInfo("UTC")) == dt.datetime(
        2019,
        1,
        1,
        0,
        0,
        tzinfo=ZoneInfo("UTC"),
    )
    assert data["temperature_air_min_0_05m"][0] == 1.5
    assert dt.datetime.fromtimestamp(int(data["timestamp"][-1]) / 1e9, tz=ZoneInfo("UTC")) == dt.datetime(
        2020,
        1,
        1,
        0,
        0,
        tzinfo=ZoneInfo("UTC"),
    )
    assert data["temperature_air_min_0_05m"][-1] == -4.6


@pytest.mark.remote
def test_export_zarr_two_datasets(
    settings_convert_units_false_wide_shape: Settings,
    tmp_path: Path,
) -> None:
    """Test that a wide frame merging two datasets is written to a named group, not the store root.

    The two datasets are daily, so they share a row and that row carries no dataset name -- there
    is no one name for it. The group is named for what the frame holds instead of for whatever its
    first row says, since a group of `None` writes the arrays into the root, where `mode="w"`
    clobbers every other group already in the store.
    """
    zarr = pytest.importorskip("zarr")
    request = DwdObservationRequest(
        parameters=[("daily", "climate_summary"), ("daily", "precipitation_more")],
        start_date="2019-01-01",
        end_date="2019-01-05",
        settings=settings_convert_units_false_wide_shape,
    ).filter_by_station_id(
        station_id=[1048],
    )
    values = request.values.all()
    filename = tmp_path.joinpath("observation.zarr")

    values.to_target(f"file://{filename}")

    root = zarr.open(filename, mode="r")
    assert list(root.array_keys()) == []
    assert list(root.group_keys()) == ["daily"]
    group = root.get("daily")
    columns = set(group.keys())
    assert "climate_summary_precipitation_amount" in columns
    assert "precipitation_more_precipitation_amount" in columns


@pytest.mark.remote
def test_export_feather(
    settings_convert_units_false_wide_shape: Settings,
    dwd_climate_summary_tabular_columns: list[str],
    tmp_path: Path,
) -> None:
    """Test export of DataFrame to feather."""
    pa_ipc = pytest.importorskip("pyarrow.ipc")
    # Request data
    request = DwdObservationRequest(
        parameters=[("daily", "climate_summary")],
        start_date="2019-01-01",
        end_date="2020-01-01",
        settings=settings_convert_units_false_wide_shape,
    ).filter_by_station_id(
        station_id=[1048],
    )
    values = request.values.all()
    # Save to Feather file.
    filename = tmp_path.joinpath("observation.feather")
    values.to_target(f"file://{filename}")
    # Read back Feather file.
    with pa_ipc.open_file(filename) as reader:
        table = reader.read_all()
    # Validate dimensions.
    assert table.num_columns == 32
    assert table.num_rows == 366
    # Validate column names.
    assert table.column_names == dwd_climate_summary_tabular_columns
    # Validate content.
    data = table.to_pydict()
    assert data["timestamp"][0] == dt.datetime(2019, 1, 1, 0, 0, tzinfo=ZoneInfo("UTC"))
    assert data["temperature_air_min_0_05m"][0] == 1.5
    assert data["timestamp"][-1] == dt.datetime(2020, 1, 1, 0, 0, tzinfo=ZoneInfo("UTC"))
    assert data["temperature_air_min_0_05m"][-1] == -4.6


@pytest.mark.remote
def test_export_sqlite(settings_convert_units_false_wide_shape: Settings, tmp_path: Path) -> None:
    """Test export of DataFrame to sqlite db."""
    request = DwdObservationRequest(
        parameters=[("daily", "climate_summary")],
        start_date="2019-01-01",
        end_date="2020-01-01",
        settings=settings_convert_units_false_wide_shape,
    ).filter_by_station_id(
        station_id=[1048],
    )
    filename = tmp_path.joinpath("observation.sqlite")
    values = request.values.all()
    values.to_target(f"sqlite:///{filename}?table=testdrive")
    connection = sqlite3.connect(filename)
    cursor = connection.cursor()
    cursor.execute("SELECT * FROM testdrive")
    results = cursor.fetchall()
    cursor.close()
    connection.close()
    first = list(results[0])
    first[3] = dt.datetime.fromisoformat(first[3])
    assert first == [
        "01048",
        "daily",
        "climate_summary",
        dt.datetime(2019, 1, 1),  # noqa: DTZ001
        19.9,
        10.0,
        8.5,
        10.0,
        0.9,
        10.0,
        8.0,
        10.0,
        0.0,
        10.0,
        0.0,
        10.0,
        7.4,
        10.0,
        7.9,
        10.0,
        991.9,
        10.0,
        5.9,
        10.0,
        84.0,
        10.0,
        7.5,
        10.0,
        2.0,
        10.0,
        1.5,
        10.0,
    ]
    last = list(results[-1])
    last[3] = dt.datetime.fromisoformat(last[3])
    assert last == [
        "01048",
        "daily",
        "climate_summary",
        dt.datetime(2020, 1, 1),  # noqa: DTZ001
        6.9,
        10.0,
        3.2,
        10.0,
        0.0,
        10.0,
        0.0,
        10.0,
        3.9,
        10.0,
        0.0,
        10.0,
        4.2,
        10.0,
        5.7,
        10.0,
        1005.1,
        10.0,
        2.4,
        10.0,
        79.0,
        10.0,
        5.6,
        10.0,
        -2.8,
        10.0,
        -4.6,
        10.0,
    ]


@pytest.mark.remote
def test_export_cratedb(
    settings_convert_units_false: Settings,
) -> None:
    """Test export of DataFrame to cratedb."""
    request = DwdObservationRequest(
        parameters=[("daily", "climate_summary")],
        periods=Period.RECENT,
        settings=settings_convert_units_false,
    ).filter_by_station_id(
        station_id=[1048],
    )
    values = request.values.all()
    with mock.patch(
        "pandas.DataFrame.to_sql",
    ) as mock_to_sql:
        values.to_target("crate://localhost/?database=test&table=testdrive")
        mock_to_sql.assert_called_once_with(
            name="testdrive",
            con="crate://localhost",
            schema="test",
            if_exists="replace",
            index=False,
            chunksize=5000,
        )


@pytest.mark.remote
def test_export_duckdb(settings_convert_units_false: Settings, tmp_path: Path) -> None:
    """Test export of DataFrame to duckdb."""
    import duckdb  # noqa: PLC0415

    request = DwdObservationRequest(
        parameters=[("daily", "climate_summary")],
        periods=Period.HISTORICAL,
        settings=settings_convert_units_false,
    ).filter_by_station_id(station_id=[1048])
    filename = tmp_path.joinpath("test.duckdb")
    values = request.values.all()
    values.to_target(f"duckdb:///{filename}?table=testdrive")
    connection = duckdb.connect(str(filename), read_only=True)
    cursor = connection.cursor()
    query = """
        SELECT
            *
        FROM
            testdrive
        WHERE
            timestamp = '1939-07-26'
            AND
            parameter = 'temperature_air_min_2m'
    """
    cursor.execute(query)
    results = cursor.fetchall()
    cursor.close()
    connection.close()
    assert results[0] == (
        "01048",
        "daily",
        "climate_summary",
        "temperature_air_min_2m",
        dt.datetime(1939, 7, 26),  # noqa: DTZ001
        10.0,
        1.0,
    )


@pytest.mark.xfail
@pytest.mark.remote
def test_export_influxdb1_wide(settings_convert_units_false_wide_shape: Settings) -> None:
    """Test export of DataFrame to influxdb v1."""
    pytest.importorskip("influxdb")
    request = DwdObservationRequest(
        parameters=[("daily", "climate_summary")],
        start_date="2019-01-01",
        settings=settings_convert_units_false_wide_shape,
    ).filter_by_station_id(station_id=[1048])
    values = request.values.all()
    mock_client = mock.MagicMock()
    with mock.patch(
        "influxdb.InfluxDBClient",
        side_effect=[mock_client],
        create=True,
    ) as mock_connect:
        values.to_target("influxdb://localhost/?database=dwd&table=weather")
        mock_connect.assert_called_once_with(
            host="localhost",
            port=8086,
            username=None,
            password=None,
            database="dwd",
            ssl=False,
        )
        mock_client.create_database.assert_called_once_with("dwd")
        mock_client.write_points.assert_called_once()
        mock_client.write_points.assert_called_with(
            points=mock.ANY,
            batch_size=50000,
        )
        points = mock_client.write_points.call_args.kwargs["points"]
        first_point = points[0]
        assert first_point["measurement"] == "weather"
        assert first_point["time"] == "2019-01-01T00:00:00.000000+00:00"
        assert first_point["tags"] == {
            "station_id": "01048",
            "dataset": "climate_summary",
            "resolution": "daily",
        }
        assert first_point["fields"] == {
            "cloud_cover_total": 7.4,
            "humidity_relative": 84.0,
            "precipitation_form": 8.0,
            "precipitation_amount": 0.9,
            "pressure_air_site": 991.9,
            "pressure_vapor": 7.9,
            "cloud_cover_total_quality": 10.0,
            "humidity_relative_quality": 10.0,
            "precipitation_form_quality": 10.0,
            "precipitation_amount_quality": 10.0,
            "pressure_air_site_quality": 10.0,
            "pressure_vapor_quality": 10.0,
            "snow_depth_quality": 10.0,
            "sunshine_duration_quality": 10.0,
            "temperature_air_max_2m_quality": 10.0,
            "temperature_air_mean_2m_quality": 10.0,
            "temperature_air_min_0_05m_quality": 10.0,
            "temperature_air_min_2m_quality": 10.0,
            "wind_gust_max_quality": 10.0,
            "wind_speed_quality": 10.0,
            "snow_depth": 0.0,
            "sunshine_duration": 0.0,
            "temperature_air_max_2m": 7.5,
            "temperature_air_mean_2m": 5.9,
            "temperature_air_min_0_05m": 1.5,
            "temperature_air_min_2m": 2.0,
            "wind_gust_max": 19.9,
            "wind_speed": 8.5,
        }


@pytest.mark.remote
def test_export_influxdb1_tidy(settings_convert_units_false: Settings) -> None:
    """Test export of DataFrame to influxdb v1."""
    pytest.importorskip("influxdb")
    request = DwdObservationRequest(
        parameters=[("daily", "climate_summary")],
        start_date="2019-01-01",
        settings=settings_convert_units_false,
    ).filter_by_station_id(station_id=[1048])
    values = request.values.all()
    mock_client = mock.MagicMock()
    with mock.patch(
        "influxdb.InfluxDBClient",
        side_effect=[mock_client],
        create=True,
    ) as mock_connect:
        values.to_target("influxdb://localhost/?database=dwd&table=weather")
        mock_connect.assert_called_once_with(
            host="localhost",
            port=8086,
            username=None,
            password=None,
            database="dwd",
            ssl=False,
        )
        mock_client.create_database.assert_called_once_with("dwd")
        mock_client.write_points.assert_called_once()
        mock_client.write_points.assert_called_with(
            points=mock.ANY,
            batch_size=50000,
        )
        points = mock_client.write_points.call_args.kwargs["points"]
        first_point = points[0]
        assert first_point["measurement"] == "weather"
        assert first_point["time"]
        assert first_point["tags"] == {
            "station_id": "01048",
            "resolution": "daily",
            "dataset": "climate_summary",
            "parameter": "cloud_cover_total",
        }
        assert first_point["fields"] == {
            "value": 7.4,
            "quality": 10.0,
        }


@pytest.mark.remote
def test_export_influxdb2_wide(settings_convert_units_false_wide_shape: Settings) -> None:
    """Test export of DataFrame to influxdb v2."""
    pytest.importorskip("influxdb_client")
    request = DwdObservationRequest(
        parameters=[("daily", "climate_summary")],
        start_date="2019-01-01",
        settings=settings_convert_units_false_wide_shape,
    ).filter_by_station_id(station_id=[1048])
    values = request.values.all()
    mock_client = mock.MagicMock()
    with (
        mock.patch(
            "influxdb_client.InfluxDBClient",
            side_effect=[mock_client],
            create=True,
        ) as mock_connect,
    ):
        values.to_target("influxdb2://orga:token@localhost/?database=dwd&table=weather")
        mock_connect.assert_called_once_with(url="http://localhost:8086", org="orga", token="token")  # noqa: S106
        mock_client.write_api.assert_called_once()
        mock_client.write_api().write.assert_called_once_with(
            bucket="dwd",
            record=mock.ANY,
        )
        points = mock_client.write_api().write.call_args.kwargs["record"]
        first_point = points[0]
        assert first_point._tags == {  # noqa: SLF001
            "station_id": "01048",
            "dataset": "climate_summary",
            "resolution": "daily",
        }
        assert first_point._fields == {
            "cloud_cover_total": 7.4,
            "humidity_relative": 84.0,
            "precipitation_form": 8.0,
            "precipitation_amount": 0.9,
            "pressure_air_site": 991.9,
            "pressure_vapor": 7.9,
            "cloud_cover_total_quality": 10.0,
            "humidity_relative_quality": 10.0,
            "precipitation_form_quality": 10.0,
            "precipitation_amount_quality": 10.0,
            "pressure_air_site_quality": 10.0,
            "pressure_vapor_quality": 10.0,
            "snow_depth_quality": 10.0,
            "sunshine_duration_quality": 10.0,
            "temperature_air_max_2m_quality": 10.0,
            "temperature_air_mean_2m_quality": 10.0,
            "temperature_air_min_0_05m_quality": 10.0,
            "temperature_air_min_2m_quality": 10.0,
            "wind_gust_max_quality": 10.0,
            "wind_speed_quality": 10.0,
            "snow_depth": 0.0,
            "sunshine_duration": 0.0,
            "temperature_air_max_2m": 7.5,
            "temperature_air_mean_2m": 5.9,
            "temperature_air_min_0_05m": 1.5,
            "temperature_air_min_2m": 2.0,
            "wind_gust_max": 19.9,
            "wind_speed": 8.5,
        }


@pytest.mark.remote
def test_export_influxdb2_tidy(settings_convert_units_false: Settings) -> None:
    """Test export of DataFrame to influxdb v2."""
    pytest.importorskip("influxdb_client")
    request = DwdObservationRequest(
        parameters=[("daily", "climate_summary")],
        start_date="2019-01-01",
        settings=settings_convert_units_false,
    ).filter_by_station_id(station_id=[1048])
    values = request.values.all()
    mock_client = mock.MagicMock()
    with (
        mock.patch(
            "influxdb_client.InfluxDBClient",
            side_effect=[mock_client],
            create=True,
        ) as mock_connect,
    ):
        values.to_target("influxdb2://orga:token@localhost/?database=dwd&table=weather")
        mock_connect.assert_called_once_with(url="http://localhost:8086", org="orga", token="token")  # noqa: S106
        mock_client.write_api.assert_called_once()
        mock_client.write_api().write.assert_called_once_with(
            bucket="dwd",
            record=mock.ANY,
        )
        points = mock_client.write_api().write.call_args.kwargs["record"]
        first_point = points[0]
        assert first_point._tags == {  # noqa: SLF001
            "station_id": "01048",
            "resolution": "daily",
            "dataset": "climate_summary",
            "parameter": "cloud_cover_total",
        }
        assert first_point._fields == {
            "value": 7.4,
            "quality": 10.0,
        }


@pytest.mark.remote
def test_export_influxdb3_wide(settings_convert_units_false_wide_shape: Settings) -> None:
    """Test export of DataFrame to influxdb v3."""
    pytest.importorskip("influxdb_client_3")
    request = DwdObservationRequest(
        parameters=[("daily", "climate_summary")],
        start_date="2019-01-01",
        settings=settings_convert_units_false_wide_shape,
    ).filter_by_station_id(station_id=[1048])
    values = request.values.all()
    with (
        mock.patch(
            "influxdb_client_3.InfluxDBClient3",
        ) as mock_client,
    ):
        values.to_target("influxdb3://orga:token@localhost/?database=dwd&table=weather")
        mock_client.assert_called_once_with(
            host="http://localhost:8181",
            org="orga",
            token="token",  # noqa: S106
            write_client_options=mock.ANY,
            database="dwd",
        )
        write_options = mock_client.call_args.kwargs["write_client_options"]["WriteOptions"]
        assert write_options.write_type.name == "synchronous"
        points = mock_client().write.call_args.kwargs["record"]
        first_point = points[0]
        assert first_point._tags == {  # noqa: SLF001
            "station_id": "01048",
            "dataset": "climate_summary",
            "resolution": "daily",
        }
        assert first_point._fields == {
            "cloud_cover_total": 7.4,
            "humidity_relative": 84.0,
            "precipitation_form": 8.0,
            "precipitation_amount": 0.9,
            "pressure_air_site": 991.9,
            "pressure_vapor": 7.9,
            "cloud_cover_total_quality": 10.0,
            "humidity_relative_quality": 10.0,
            "precipitation_form_quality": 10.0,
            "precipitation_amount_quality": 10.0,
            "pressure_air_site_quality": 10.0,
            "pressure_vapor_quality": 10.0,
            "snow_depth_quality": 10.0,
            "sunshine_duration_quality": 10.0,
            "temperature_air_max_2m_quality": 10.0,
            "temperature_air_mean_2m_quality": 10.0,
            "temperature_air_min_0_05m_quality": 10.0,
            "temperature_air_min_2m_quality": 10.0,
            "wind_gust_max_quality": 10.0,
            "wind_speed_quality": 10.0,
            "snow_depth": 0.0,
            "sunshine_duration": 0.0,
            "temperature_air_max_2m": 7.5,
            "temperature_air_mean_2m": 5.9,
            "temperature_air_min_0_05m": 1.5,
            "temperature_air_min_2m": 2.0,
            "wind_gust_max": 19.9,
            "wind_speed": 8.5,
        }


@pytest.mark.remote
def test_export_influxdb3_tidy(settings_convert_units_false: Settings) -> None:
    """Test export of DataFrame to influxdb v3."""
    pytest.importorskip("influxdb_client_3")
    request = DwdObservationRequest(
        parameters=[("daily", "climate_summary")],
        start_date="2019-01-01",
        settings=settings_convert_units_false,
    ).filter_by_station_id(station_id=[1048])
    values = request.values.all()
    with (
        mock.patch(
            "influxdb_client_3.InfluxDBClient3",
        ) as mock_client,
    ):
        values.to_target("influxdb3://orga:token@localhost/?database=dwd&table=weather")
        mock_client.assert_called_once_with(
            host="http://localhost:8181",
            org="orga",
            database="dwd",
            token="token",  # noqa: S106
            write_client_options=mock.ANY,
        )
        points = mock_client().write.call_args.kwargs["record"]
        first_point = points[0]
        assert first_point._tags == {  # noqa: SLF001
            "station_id": "01048",
            "resolution": "daily",
            "dataset": "climate_summary",
            "parameter": "cloud_cover_total",
        }
        assert first_point._fields == {
            "value": 7.4,
            "quality": 10.0,
        }


# test for to_target with if_exists parameter, use duckdb for simplicity.
# Every one of these tells its two writes apart by the station id in the frame and asserts on
# `SELECT DISTINCT station_id`, so what a request contributed was a one-station frame and a slow
# way to get a second string. `_one_row` below supplies both without a station lookup (GH-2003).
def test_export_duckdb_if_exists_fail(
    tmp_path: Path,
) -> None:
    """Test export of DataFrame to duckdb with if_exists parameter."""
    pytest.importorskip("duckdb")

    filename = tmp_path.joinpath("test.duckdb")
    _one_row().to_target(f"duckdb:///{filename}?table=testdrive")
    # Second export with if_exists='fail' should raise an error
    with pytest.raises(ExportRefusedError) as exec_info:
        _one_row().to_target(f"duckdb:///{filename}?table=testdrive", if_exists="fail")
    assert exec_info.match("Table 'testdrive' already exists in the database, aborting write due to if_exists='fail'.")


def test_export_duckdb_if_exists_replace(
    tmp_path: Path,
) -> None:
    """Test export of DataFrame to duckdb with if_exists='replace' parameter."""
    duckdb = pytest.importorskip("duckdb")

    filename = tmp_path.joinpath("test.duckdb")

    _one_row("01048").to_target(f"duckdb:///{filename}?table=testdrive")

    # Verify that the table exists and has station_id 1048
    conn = duckdb.connect(str(filename), read_only=False)
    assert conn.execute("SELECT DISTINCT station_id FROM testdrive").fetchall() == [("01048",)]

    # a stations-shaped frame, as this one has always written second: `replace` drops the table
    # before it writes, so the replacement is free not to match the schema it replaces
    stations = ExportMixin(df=pl.DataFrame({"station_id": ["01050"], "name": ["Grossenkneten"]}))
    stations.to_target(f"duckdb:///{filename}?table=testdrive", if_exists="replace")
    # Verify that the table exists and has station_id 1050
    assert conn.execute("SELECT DISTINCT station_id FROM testdrive").fetchall() == [("01050",)]


def test_export_duckdb_if_exists_append(
    tmp_path: Path,
) -> None:
    """Test export of DataFrame to duckdb with if_exists='append' parameter."""
    duckdb = pytest.importorskip("duckdb")

    filename = tmp_path.joinpath("test.duckdb")

    _one_row("01048").to_target(f"duckdb:///{filename}?table=testdrive")

    # Verify that the table exists and has station_id 1048
    conn = duckdb.connect(str(filename), read_only=False)
    assert conn.execute("SELECT DISTINCT station_id FROM testdrive").fetchall()[0] == ("01048",)

    _one_row("01050").to_target(f"duckdb:///{filename}?table=testdrive", if_exists="append")
    # Verify that the table has entries for both station_ids
    assert conn.execute("SELECT DISTINCT station_id FROM testdrive ORDER BY station_id").fetchall() == [
        ("01048",),
        ("01050",),
    ]


def test_export_duckdb_if_exists_skip(
    tmp_path: Path,
) -> None:
    """Test export of DataFrame to duckdb with if_exists='skip' parameter."""
    duckdb = pytest.importorskip("duckdb")

    filename = tmp_path.joinpath("test.duckdb")

    _one_row("01048").to_target(f"duckdb:///{filename}?table=testdrive")

    # Verify that the table exists and has station_id 1048
    conn = duckdb.connect(str(filename), read_only=False)
    assert conn.execute("SELECT DISTINCT station_id FROM testdrive").fetchall() == [("01048",)]

    _one_row("01050").to_target(f"duckdb:///{filename}?table=testdrive", if_exists="skip")
    # Verify that the table still only has station_id 1048
    assert conn.execute("SELECT DISTINCT station_id FROM testdrive").fetchall() == [("01048",)]


# The four below stay on a real request: `_one_row` would make them byte-identical to the
# `if_exists` tests above, and the per-station frames `values.query()` yields and the whole
# frame `values.all()` hands to `to_target` are what their names are about (GH-2003).
@pytest.mark.remote
def test_export_duckdb_single_query_results_if_exists_replace(tmp_path: Path) -> None:
    """Test export of DataFrame to duckdb with if_exists='replace' parameter."""
    duckdb = pytest.importorskip("duckdb")

    filename = tmp_path.joinpath("test.duckdb")

    request = DwdObservationRequest(
        parameters=[("daily", "climate_summary")],
    ).filter_by_station_id(station_id=[1048, 1050])

    values_query = request.values.query()

    result_1048 = next(values_query)
    result_1048.to_target(f"duckdb:///{filename}?table=testdrive", if_exists="replace")

    # Verify that the table exists and has station_id 1048
    conn = duckdb.connect(str(filename), read_only=False)
    assert conn.execute("SELECT DISTINCT station_id FROM testdrive").fetchall() == [("01048",)]

    result_1050 = next(values_query)
    result_1050.to_target(f"duckdb:///{filename}?table=testdrive", if_exists="replace")

    # Verify that the table exists and has station_id 1050
    assert conn.execute("SELECT DISTINCT station_id FROM testdrive").fetchall() == [("01050",)]


@pytest.mark.remote
def test_export_duckdb_single_query_results_if_exists_append(tmp_path: Path) -> None:
    """Test export of DataFrame to duckdb with if_exists='append' parameter."""
    duckdb = pytest.importorskip("duckdb")

    filename = tmp_path.joinpath("test.duckdb")

    request = DwdObservationRequest(
        parameters=[("daily", "climate_summary")],
    ).filter_by_station_id(station_id=[1048, 1050])

    values_query = request.values.query()

    result_1048 = next(values_query)
    result_1048.to_target(f"duckdb:///{filename}?table=testdrive", if_exists="append")

    # Verify that the table exists and has station_id 1048
    conn = duckdb.connect(str(filename), read_only=False)
    assert conn.execute("SELECT DISTINCT station_id FROM testdrive").fetchall() == [("01048",)]

    result_1050 = next(values_query)
    result_1050.to_target(f"duckdb:///{filename}?table=testdrive", if_exists="append")

    # Verify that the table has entries for both station_ids
    assert conn.execute("SELECT DISTINCT station_id FROM testdrive ORDER BY station_id").fetchall() == [
        ("01048",),
        ("01050",),
    ]


@pytest.mark.remote
def test_export_duckdb_all_result_if_exists_replace(tmp_path: Path) -> None:
    """Test export of DataFrame to duckdb with if_exists='replace' parameter."""
    duckdb = pytest.importorskip("duckdb")

    filename = tmp_path.joinpath("test.duckdb")

    request = DwdObservationRequest(
        parameters=[("daily", "climate_summary")],
    ).filter_by_station_id(station_id=[1048])

    values = request.values.all()
    values.to_target(f"duckdb:///{filename}?table=testdrive", if_exists="replace")

    # Verify that the table exists and has station_id 1048
    conn = duckdb.connect(str(filename), read_only=False)
    assert conn.execute("SELECT DISTINCT station_id FROM testdrive").fetchall() == [("01048",)]

    request = DwdObservationRequest(
        parameters=[("daily", "climate_summary")],
    ).filter_by_station_id(station_id=[1050])

    values = request.values.all()
    values.to_target(f"duckdb:///{filename}?table=testdrive", if_exists="replace")

    # Verify that the table exists and has station_id 1050
    assert conn.execute("SELECT DISTINCT station_id FROM testdrive").fetchall() == [("01050",)]


@pytest.mark.remote
def test_export_duckdb_all_result_if_exists_append(tmp_path: Path) -> None:
    """Test export of DataFrame to duckdb with if_exists='append' parameter."""
    duckdb = pytest.importorskip("duckdb")

    filename = tmp_path.joinpath("test.duckdb")

    request = DwdObservationRequest(
        parameters=[("daily", "climate_summary")],
    ).filter_by_station_id(station_id=[1048])

    values = request.values.all()
    values.to_target(f"duckdb:///{filename}?table=testdrive", if_exists="append")

    # Verify that the table exists and has station_id 1048
    conn = duckdb.connect(str(filename), read_only=False)
    assert conn.execute("SELECT DISTINCT station_id FROM testdrive").fetchall() == [("01048",)]

    request = DwdObservationRequest(
        parameters=[("daily", "climate_summary")],
    ).filter_by_station_id(station_id=[1050])

    values = request.values.all()
    values.to_target(f"duckdb:///{filename}?table=testdrive", if_exists="append")

    # Verify that the table exists and has station_id 1050
    assert conn.execute("SELECT DISTINCT station_id FROM testdrive ORDER BY station_id").fetchall() == [
        ("01048",),
        ("01050",),
    ]


def _one_row(station_id: str = "01048") -> ExportMixin:
    """Build the smallest frame a sink will write, so it is reached without a request behind it.

    The station id is an argument because the `if_exists` tests tell two writes apart by it, and
    asking upstream for a second station is a slow way to obtain a different string.
    """
    return ExportMixin(
        df=pl.DataFrame(
            {
                "station_id": [station_id],
                "resolution": ["daily"],
                "dataset": ["climate_summary"],
                "parameter": ["temperature_air_mean_2m"],
                "timestamp": [dt.datetime(2020, 1, 1, tzinfo=ZoneInfo("UTC"))],
                "value": [1.0],
                "quality": [1.0],
            },
        ),
    )


def test_export_file_excel_if_exists_replace(tmp_path: Path) -> None:
    """Test export of DataFrame to Excel file with if_exists='replace' parameter."""
    pytest.importorskip("xlsxwriter")

    filename = tmp_path.joinpath("testfile.xlsx")

    _one_row().to_target(f"file:///{filename}", if_exists="replace")
    assert filename.exists()


def test_export_file_append_exception() -> None:
    """Test export of DataFrame to file with if_exists='append' parameter."""
    with pytest.raises(ExportRefusedError) as exec_info:
        _one_row().to_target("file:///foo", if_exists="append")
    assert exec_info.match("Append mode is not supported for file exports.")


@pytest.mark.skipif(
    condition=IS_CI and IS_WINDOWS, reason="File existence check behaves differently on Windows CI environments."
)
def test_export_file_fail_exception(tmp_path: Path) -> None:
    """Test export of DataFrame to file with if_exists='fail' parameter."""
    filename = tmp_path.joinpath("testfile")
    filename.write_text("foo")

    with pytest.raises(ExportRefusedError) as exec_info:
        _one_row().to_target(f"file:///{filename}", if_exists="fail")
    assert exec_info.match("File '.*testfile' already exists, aborting write due to if_exists='fail'.")


@pytest.mark.parametrize(
    ("if_exists", "refused"),
    [
        pytest.param("replace", False, id="replace"),
        pytest.param("append", False, id="append"),
        pytest.param("fail", True, id="fail"),
        pytest.param("skip", True, id="skip"),
    ],
)
def test_influxdb_takes_the_modes_that_describe_what_it_does(if_exists: str, refused: bool) -> None:  # noqa: FBT001
    """InfluxDB refused `append`, which is the one word for what it actually does.

    That refusal made the batch export impossible rather than merely awkward:
    `TimeseriesValues.to_target` writes its first station with the `if_exists` it was given and
    every station after it with `append`, so no argument let a multi-station request reach InfluxDB
    -- and the export docs shipped three examples doing exactly that, broken from the day the
    argument was added. `fail` and `skip` stay refused because both turn on whether the measurement
    already exists, which this sink never asks.
    """
    pytest.importorskip("influxdb")
    client = mock.MagicMock()

    with mock.patch("influxdb.InfluxDBClient", side_effect=[client], create=True):
        if refused:
            with pytest.raises(ExportRefusedError, match=f"if_exists='{if_exists}' is not supported for InfluxDB"):
                _one_row().to_target("influxdb://localhost/?database=dwd&table=weather", if_exists=if_exists)
            return
        _one_row().to_target("influxdb://localhost/?database=dwd&table=weather", if_exists=if_exists)

    assert client.write_points.call_count == 1


def test_duckdb_append_matches_columns_by_name(tmp_path: Path) -> None:
    """Appending a frame whose columns are named differently is refused, not filed by position.

    `INSERT INTO t SELECT * FROM origin` matches by position, so two runs carrying the same number
    of columns under different names were both accepted and the second one's values landed under
    the first one's headings. A `--shape=wide` schedule reaches that by changing one parameter: a
    day's precipitation was stored as its temperature, exit 0 and nothing said.
    """
    duckdb = pytest.importorskip("duckdb")
    target = f"duckdb:///{tmp_path / 'obs.duckdb'}?table=weather"
    temperature = pl.DataFrame({"timestamp": ["2020-01-01"], "temperature_air_mean_2m": [10.1]})
    precipitation = pl.DataFrame({"timestamp": ["2020-01-01"], "precipitation_amount": [0.0]})

    ExportMixin(df=temperature).to_target(target)
    with pytest.raises(duckdb.BinderException, match='does not have a column with name "precipitation_amount"'):
        ExportMixin(df=precipitation).to_target(target, if_exists="append")

    connection = duckdb.connect(str(tmp_path / "obs.duckdb"))
    assert connection.execute("SELECT COUNT(*) FROM weather").fetchone()[0] == 1, "the refused append still wrote"
    # the same names still append, which is what a schedule of one query does
    ExportMixin(df=temperature).to_target(target, if_exists="append")
    assert connection.execute("SELECT COUNT(*) FROM weather").fetchone()[0] == 2


@pytest.mark.parametrize(
    ("target", "connects_to"),
    [
        pytest.param(
            "postgresql+psycopg://u:p@localhost/dwd?table=weather&sslmode=require",
            "postgresql+psycopg://u:p@localhost/dwd?sslmode=require",
            id="postgresql",
        ),
        pytest.param(
            "mysql://u:p@localhost/dwd?charset=utf8mb4&table=weather",
            "mysql://u:p@localhost/dwd?charset=utf8mb4",
            id="mysql",
        ),
    ],
)
@pytest.mark.parametrize("if_exists", ["replace", "fail"])
def test_sql_sink_keeps_the_table_out_of_the_connection(
    target: str,
    connects_to: str,
    if_exists: str,
    tmp_path: Path,
) -> None:
    """`?table=` names the table and no longer reaches the driver as a connection option.

    The sink handed the whole target to SQLAlchemy, which passes every query argument to the
    driver's `connect`; psycopg, psycopg2, mysqlclient and pymysql all refuse `table`, so no
    `postgresql://` or `mysql://` target could connect, whatever `if_exists` said. sqlite ignores
    an argument it does not know, which is why the sqlite sink looked healthy. No server is needed:
    the engine handed back is a sqlite file, and what is read is the URL the sink asked for it with.
    """
    sqlalchemy = pytest.importorskip("sqlalchemy")
    pytest.importorskip("pandas")
    database = tmp_path / "obs.sqlite"
    create_engine = sqlalchemy.create_engine
    asked = []

    def engine_for(url: object, **kwargs: object) -> object:
        asked.append(url)
        return create_engine(f"sqlite:///{database}", **kwargs)

    with mock.patch("sqlalchemy.create_engine", side_effect=engine_for):
        _one_row().to_target(target, if_exists=if_exists)

    assert [sqlalchemy.make_url(url).render_as_string(hide_password=False) for url in asked] == [connects_to]
    connection = sqlite3.connect(database)
    try:
        assert connection.execute("SELECT station_id FROM weather").fetchall() == [("01048",)]
    finally:
        connection.close()


def _urls_the_sink_asks_for(sqlalchemy: object, target: str, tmp_path: Path, frame: ExportMixin | None = None) -> list:
    """Write through the SQL sink to a sqlite file, and return the URLs it asked SQLAlchemy for."""
    database = tmp_path / "obs.sqlite"
    create_engine = sqlalchemy.create_engine
    asked = []

    def engine_for(url: object, **kwargs: object) -> object:
        asked.append(url)
        return create_engine(f"sqlite:///{database}", **kwargs)

    with mock.patch("sqlalchemy.create_engine", side_effect=engine_for):
        (frame or _one_row()).to_target(target)
    return [sqlalchemy.make_url(url).render_as_string(hide_password=False) for url in asked]


@pytest.mark.parametrize(
    ("target", "psycopg", "connects_to"),
    [
        pytest.param(
            "postgresql://u:p@localhost/dwd?table=weather",
            True,
            "postgresql+psycopg://u:p@localhost/dwd",
            id="bare",
        ),
        pytest.param(
            "postgresql://u:p@localhost/dwd?table=weather",
            False,
            "postgresql://u:p@localhost/dwd",
            id="bare-without-psycopg",
        ),
        pytest.param(
            "postgresql+psycopg2://u:p@localhost/dwd?table=weather",
            True,
            "postgresql+psycopg2://u:p@localhost/dwd",
            id="psycopg2",
        ),
        pytest.param(
            "postgresql+pg8000://u:p@localhost/dwd?table=weather",
            True,
            "postgresql+pg8000://u:p@localhost/dwd",
            id="pg8000",
        ),
    ],
)
def test_sql_sink_names_psycopg_for_a_bare_postgresql_target(
    target: str,
    psycopg: bool,  # noqa: FBT001
    connects_to: str,
    tmp_path: Path,
) -> None:
    """A bare `postgresql://` asks for psycopg 3, the driver the `postgresql` extra installs.

    SQLAlchemy 2.0 resolves that URL to psycopg2 and 2.1 to psycopg 3, and 2.1 needs Python 3.11,
    so which driver a target needed depended on the Python it ran on: with the extra's psycopg2,
    2.1 failed with `No module named 'psycopg'`. A target that names its driver keeps it, and
    without psycopg 3 installed the URL is left to SQLAlchemy, so psycopg2 alone still serves 2.0.
    """
    sqlalchemy = pytest.importorskip("sqlalchemy")
    pytest.importorskip("pandas")
    with mock.patch("wetterdienst.io.export._psycopg_imports", return_value=psycopg):
        assert _urls_the_sink_asks_for(sqlalchemy, target, tmp_path) == [connects_to]


@pytest.mark.parametrize(
    ("target", "rows_per_insert"),
    [
        pytest.param("postgresql+psycopg://u:p@localhost/dwd?table=weather", 65535 // 30, id="postgresql"),
        pytest.param("mysql://u:p@localhost/dwd?table=weather", 5000, id="mysql"),
    ],
)
def test_sql_sink_keeps_a_postgresql_insert_within_65535_parameters(
    target: str,
    rows_per_insert: int,
    tmp_path: Path,
) -> None:
    """A wide frame goes to PostgreSQL in inserts of at most 65535 values.

    psycopg 3 binds parameters on the server, which takes at most 65535 a statement, and the sink's
    multi-row inserts of 5000 rows carry one per cell: from 14 columns on, a `--shape=wide` export
    failed partway through. psycopg2 interpolated them on the client and never met the limit.
    """
    sqlalchemy = pytest.importorskip("sqlalchemy")
    pandas = pytest.importorskip("pandas")
    frame = ExportMixin(df=pl.DataFrame({f"column_{i}": [i] for i in range(30)}))
    to_sql = pandas.DataFrame.to_sql
    with mock.patch.object(pandas.DataFrame, "to_sql", autospec=True, side_effect=to_sql) as spy:
        _urls_the_sink_asks_for(sqlalchemy, target, tmp_path, frame)
    assert spy.call_args.kwargs["chunksize"] == rows_per_insert


@pytest.mark.parametrize(("extra", "driver"), [("mysql", "mysqlclient"), ("postgresql", "psycopg[binary]")])
def test_sql_extras_carry_what_the_sink_imports(extra: str, driver: str) -> None:
    """`pip install wetterdienst[mysql]` or `[postgresql]` alone is enough for its target.

    The generic SQL sink imports SQLAlchemy and writes through pandas, which only the `export`
    extra brought, so either extra on its own ended in `No module named 'sqlalchemy'` -- after
    the download. psycopg comes with `[binary]`, its own libpq, so no system one is needed.
    """
    pyproject = tomllib.loads((Path(__file__).parent.parent / "pyproject.toml").read_text(encoding="utf8"))
    requirements = pyproject["project"]["optional-dependencies"][extra]
    names = {re.match(r"[A-Za-z0-9_.\[\]-]+", requirement).group(0).lower() for requirement in requirements}
    assert {"pandas", "sqlalchemy", driver} <= names


def test_psycopg_counts_as_installed_only_when_it_imports() -> None:
    """An installed psycopg 3 without a libpq to call is not taken for a bare `postgresql://`.

    Its pure-Python package is found on the path but fails on import with `no pq wrapper
    available`, so naming it would turn a URL psycopg2 could serve into an `ImportError`.
    """
    from wetterdienst.io.export import _psycopg_imports  # noqa: PLC0415

    with mock.patch("importlib.import_module", side_effect=ImportError("no pq wrapper available")) as probe:
        assert not _psycopg_imports()
    probe.assert_called_once_with("psycopg")
    with mock.patch("importlib.import_module", return_value=mock.sentinel.psycopg) as probe:
        assert _psycopg_imports()
    probe.assert_called_once_with("psycopg")


@pytest.mark.parametrize(
    ("target", "datetime_type"),
    [
        pytest.param("mysql://u:p@localhost/dwd?table=weather", "DATETIME", id="mysql"),
        pytest.param("mysql+pymysql://u:p@localhost/dwd?table=weather", "DATETIME", id="mysql+pymysql"),
        pytest.param("mariadb://u:p@localhost/dwd?table=weather", "DATETIME", id="mariadb"),
        # a dialect built on MySQL's under a name of its own, as TiDB's or SingleStore's are
        pytest.param("wdmysqlfork://u:p@localhost/dwd?table=weather", "DATETIME", id="mysql-derived"),
        # the control: PostgreSQL's `timestamptz` holds any year and keeps the zone, so it is left alone
        pytest.param(
            "postgresql+pg8000://u:p@localhost/dwd?table=weather", "TIMESTAMP WITH TIME ZONE", id="postgresql"
        ),
    ],
)
def test_sql_sink_writes_mysql_datetimes_as_naive_utc(
    target: str, datetime_type: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A MySQL or MariaDB table gets `DATETIME` columns holding UTC, so a year before 1970 fits.

    pandas maps a zoned datetime to `TIMESTAMP(timezone=True)`, which the MySQL dialect compiles
    to a plain `TIMESTAMP`; that type starts in 1970, so the first row of a historical DWD series
    was refused (strict mode) or stored as zeros. No server is needed: the engine carries the
    target's dialect over a stand-in driver, `to_sql` is stubbed, and the frame it is handed is
    compiled into the `CREATE TABLE` that dialect would send.
    """
    sqlalchemy = pytest.importorskip("sqlalchemy")
    pd = pytest.importorskip("pandas")
    from pandas.io.sql import SQLDatabase, SQLTable  # noqa: PLC0415
    from sqlalchemy.dialects import registry  # noqa: PLC0415
    from sqlalchemy.dialects.mysql.pymysql import MySQLDialect_pymysql  # noqa: PLC0415
    from sqlalchemy.schema import CreateTable  # noqa: PLC0415

    class ForkDialect(MySQLDialect_pymysql):
        name = "wdmysqlfork"

    monkeypatch.setitem(registry.impls, "wdmysqlfork", lambda: ForkDialect)
    # `start_date` and `end_date` stand for the station frame's other datetime columns, the latter
    # empty as an active station's is. Midnight in Berlin in 1850 is 23:06:32 UTC the day before
    # (local mean time), so a zone dropped without converting to UTC first would show
    export = ExportMixin(
        df=pl.DataFrame(
            {
                "station_id": ["01048"],
                "timestamp": [dt.datetime(1850, 1, 1, tzinfo=ZoneInfo("UTC"))],
                "start_date": [dt.datetime(1850, 1, 1, tzinfo=ZoneInfo("Europe/Berlin"))],
                "end_date": pl.Series([None], dtype=pl.Datetime("us", "UTC")),
                "value": [1.0],
            }
        )
    )
    create_engine = sqlalchemy.create_engine
    engines = []
    handed = []

    def engine_for(url: object, **kwargs: object) -> object:
        # the target's real dialect, with a stand-in driver: nothing connects before `to_sql`
        engines.append(create_engine(url, module=mock.MagicMock(), **kwargs))
        return engines[-1]

    def to_sql(frame: object, **_kwargs: object) -> None:
        handed.append(frame)

    with (
        mock.patch("sqlalchemy.create_engine", side_effect=engine_for),
        mock.patch.object(pd.DataFrame, "to_sql", autospec=True, side_effect=to_sql),
    ):
        export.to_target(target)

    ((engine,), (frame,)) = engines, handed
    with SQLDatabase(create_engine("sqlite://")) as database:
        table = SQLTable("weather", database, frame=frame, index=False).table
        ddl = str(CreateTable(table).compile(dialect=engine.dialect))
    assert f"timestamp {datetime_type}" in ddl
    assert f"start_date {datetime_type}" in ddl
    assert f"end_date {datetime_type}" in ddl
    assert frame["end_date"].isna().tolist() == [True]
    if datetime_type == "DATETIME":
        assert frame["timestamp"].tolist() == [pd.Timestamp("1850-01-01 00:00:00")]
        assert frame["start_date"].tolist() == [pd.Timestamp("1849-12-31 23:06:32")]
    else:
        assert frame["timestamp"].tolist() == [pd.Timestamp("1850-01-01 00:00:00", tz="UTC")]
        # compared as an instant: pandas rounds Berlin's 1850 offset to whole minutes when it builds one
        assert isinstance(frame["start_date"].dtype, pd.DatetimeTZDtype)
        assert str(frame["start_date"].dtype.tz) == "Europe/Berlin"
        assert frame["start_date"].dt.tz_convert("UTC").tolist() == [pd.Timestamp("1849-12-31 23:06:32", tz="UTC")]


def _gauge_stations_result() -> StationsResult:
    """Build a stations result from a request declaring gauge_zero, as WSV Pegelonline's does.

    Three stations: one with an elevation, one without, and one without an elevation but with a
    gauge zero. They also carry the `distance` a rank filter adds, which the provider does not
    declare.
    """

    class GaugeRequestMock:
        _base_columns = (*TimeseriesRequest._base_columns, "gauge_zero")  # noqa: SLF001

    station = {"resolution": "15_minutes", "dataset": "data", "start_date": None, "end_date": None, "region": None}
    df = pl.DataFrame(
        [
            {**station, "station_id": "a", "latitude": 50.0, "longitude": 8.0, "elevation": 100.0, "name": "A"},
            {**station, "station_id": "b", "latitude": 51.0, "longitude": 9.0, "elevation": None, "name": "B"},
            {**station, "station_id": "c", "latitude": 52.0, "longitude": 10.0, "elevation": None, "name": "C"},
        ],
        schema={
            "resolution": pl.String,
            "dataset": pl.String,
            "station_id": pl.String,
            "start_date": pl.Datetime(time_zone="UTC"),
            "end_date": pl.Datetime(time_zone="UTC"),
            "latitude": pl.Float64,
            "longitude": pl.Float64,
            "elevation": pl.Float64,
            "name": pl.String,
            "region": pl.String,
        },
        orient="row",
    ).with_columns(gauge_zero=pl.Series([None, None, -1.809], dtype=pl.Float64), distance=pl.lit(1.0))
    return StationsResult(df=df, df_all=df, stations_filter=StationsFilter.ALL, stations=GaugeRequestMock())


# per station id: the feature's position and its gauge_zero property
_GAUGE_FEATURES = {
    "a": ([8.0, 50.0, 100.0], None),
    "b": ([9.0, 51.0], None),
    "c": ([10.0, 52.0], -1.809),
}


def test_stations_to_ogc_feature_collection_without_elevation_and_with_gauge_zero() -> None:
    """A station without an elevation gets a 2D position, and gauge_zero reaches its properties.

    RFC 7946 3.1.1 makes a position two or more numbers, so `[lon, lat, null]` is not one.
    """
    features = _gauge_stations_result().to_ogc_feature_collection()["data"]["features"]
    assert {
        feature["properties"]["id"]: (feature["geometry"]["coordinates"], feature["properties"]["gauge_zero"])
        for feature in features
    } == _GAUGE_FEATURES
    # a column a filter adds is not one the provider declares
    assert not any("distance" in feature["properties"] for feature in features)


def test_values_to_ogc_feature_collection_without_elevation_and_with_gauge_zero() -> None:
    """The values variant positions and describes its stations the same way."""
    df_values = pl.DataFrame(
        [
            {
                "station_id": station_id,
                "resolution": "15_minutes",
                "dataset": "data",
                "parameter": "stage",
                "timestamp": dt.datetime(2026, 1, 1, tzinfo=ZoneInfo("UTC")),
                "value": value,
                "quality": None,
            }
            for value, station_id in enumerate(_GAUGE_FEATURES)
        ],
        schema_overrides={"quality": pl.Float64},
        orient="row",
    )
    # station_id as Enum, as a real values frame has it
    df_values = TimeseriesValues._cast_metadata_to_enum(df_values)  # noqa: SLF001
    result = ValuesResult(stations=_gauge_stations_result(), values=None, df=df_values)
    features = json.loads(result.to_geojson())["data"]["features"]
    assert {
        feature["properties"]["id"]: (feature["geometry"]["coordinates"], feature["properties"]["gauge_zero"])
        for feature in features
    } == _GAUGE_FEATURES
    # each feature carries its own station's value
    assert {feature["properties"]["id"]: [v["value"] for v in feature["values"]] for feature in features} == {
        "a": [0.0],
        "b": [1.0],
        "c": [2.0],
    }


@pytest.mark.parametrize(
    ("target", "secret", "logged", "stubs"),
    [
        pytest.param(
            "postgresql+psycopg2://scott:tiger-secret@db.example.org:5432/dwd?table=weather&sslmode=require",
            "tiger-secret",
            "postgresql+psycopg2://scott:***@db.example.org:5432/dwd?table=weather&sslmode=require",
            ["sqlalchemy.create_engine", "pandas.DataFrame.to_sql"],
            id="sql",
        ),
        pytest.param(
            "influxdb2://acme:SECRET-TOKEN==@localhost/?database=dwd&table=weather",
            "SECRET-TOKEN",
            "influxdb2://acme:***@localhost/?database=dwd&table=weather",
            ["influxdb_client.InfluxDBClient"],
            id="influxdb2",
        ),
        pytest.param(
            "influxdb3://acme:SECRET-TOKEN==@eu-central-1-1.aws.cloud2.influxdata.com/?database=dwd&table=weather",
            "SECRET-TOKEN",
            "influxdb3://acme:***@eu-central-1-1.aws.cloud2.influxdata.com/?database=dwd&table=weather",
            ["influxdb_client_3.InfluxDBClient3"],
            id="influxdb3",
        ),
        pytest.param(
            "crate://crate:hunter2-secret@localhost:4200/dwd?table=weather",
            "hunter2-secret",
            "crate://crate:***@localhost:4200/dwd?table=weather",
            ["pandas.DataFrame.to_sql"],
            id="crate",
        ),
    ],
)
def test_to_target_logs_the_target_without_its_password(
    target: str,
    secret: str,
    logged: str,
    stubs: list[str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The target is logged with its password slot as `***`, and the rest of it as given.

    `to_target` logged the target verbatim at INFO, which the CLI shows by default, so a password,
    or the API token the documented InfluxDB 2/3 spelling carries in the password slot, went to
    stderr and from there into cron mail, journald or a CI log. No sink is reached: each driver is
    stubbed, and what is read is the log.
    """
    with contextlib.ExitStack() as stack:
        for stub in stubs:
            # each case skips on the driver it needs, not on another case's
            pytest.importorskip(stub.split(".")[0])
            stack.enter_context(mock.patch(stub))
        stack.enter_context(caplog.at_level(logging.INFO, logger="wetterdienst"))
        _one_row().to_target(target)

    assert secret not in caplog.text
    assert f"Exporting records to {logged}" in caplog.text
    if target.startswith("crate://"):
        assert f"Writing to CrateDB. target={logged}, table=weather" in caplog.text


def test_timeseries_values_to_target_logs_the_target_without_its_password(caplog: pytest.LogCaptureFixture) -> None:
    """The line the multi-station export logs after each station shows the target redacted too."""
    target = "influxdb2://acme:SECRET-TOKEN@localhost/?database=dwd&table=weather"
    result = mock.MagicMock()
    result.df = pl.DataFrame({"station_id": ["01048"]})
    values = mock.MagicMock()
    values.query.return_value = iter([result])
    values.sr.station_id = ["01048"]

    with caplog.at_level(logging.INFO, logger="wetterdienst"):
        TimeseriesValues.to_target(values, target)

    # the sink is still handed the target with its token, which it needs to connect
    result.to_target.assert_called_once_with(target, if_exists="fail")
    assert "SECRET-TOKEN" not in caplog.text
    assert (
        "Exported data for station 01048 to influxdb2://acme:***@localhost/?database=dwd&table=weather." in caplog.text
    )


@pytest.mark.parametrize(
    ("target", "pieces"),
    [
        # SQLAlchemy's reading ends the password at the first `@`, which left `tok3n-TAIL@localhost`
        # as the host
        pytest.param(
            "influxdb2://acme:tok3n-HEAD@tok3n-TAIL@localhost/?database=dwd&table=weather",
            ["tok3n-HEAD", "tok3n-TAIL"],
            id="influxdb2-at",
        ),
        pytest.param(
            "crate://crate:hun-HEAD@ter-TAIL@localhost:4200/dwd?table=weather",
            ["hun-HEAD", "ter-TAIL"],
            id="crate-at",
        ),
        # `make_url` raised `invalid literal for int() with base 10: 'pw-TAIL@db'`
        pytest.param(
            "postgresql://scott:pw-HEAD@ss:pw-TAIL@db/dwd?table=weather",
            ["pw-HEAD", "pw-TAIL"],
            id="sql-at-then-colon",
        ),
    ],
)
def test_to_target_refuses_a_password_holding_an_unencoded_at(
    target: str,
    pieces: list[str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A password whose `@` would be read as the end of it is refused before anything is logged.

    Read that way, the rest of it became the host and port, which a driver's error then printed.
    """
    with (
        caplog.at_level(logging.DEBUG, logger="wetterdienst"),
        pytest.raises(ExportRefusedError, match="%40") as excinfo,
    ):
        _one_row().to_target(target)

    # refused first, so nothing was logged and nothing connected
    assert caplog.text == ""
    for piece in pieces:
        assert piece not in str(excinfo.value)


# a password holding every delimiter `urlparse` ends the host part at, and a colon
_DELIMITED = "p/a?s#s:w"


def test_to_target_writes_influxdb1_with_a_password_holding_delimiters() -> None:
    """InfluxDB 1 is handed the host, port, password and database the target names."""
    pytest.importorskip("influxdb")
    with mock.patch("influxdb.InfluxDBClient") as client:
        _one_row().to_target(f"influxdb://root:{_DELIMITED}@localhost:8087/?database=obs")

    client.assert_called_once_with(
        host="localhost", port=8087, username="root", password=_DELIMITED, database="obs", ssl=False
    )


def test_to_target_writes_influxdb2_with_a_token_holding_delimiters() -> None:
    """InfluxDB 2 is handed the URL, org and token the target names, and writes to its bucket."""
    pytest.importorskip("influxdb_client")
    with mock.patch("influxdb_client.InfluxDBClient") as client:
        _one_row().to_target(f"influxdb2://acme:{_DELIMITED}@localhost/?database=obs&table=weather")

    client.assert_called_once_with(url="http://localhost:8086", org="acme", token=_DELIMITED)
    assert client.return_value.write_api.return_value.write.call_args.kwargs["bucket"] == "obs"


def test_to_target_writes_influxdb3_with_a_token_holding_delimiters() -> None:
    """InfluxDB 3 is handed the host, org, token and database the target names."""
    pytest.importorskip("influxdb_client_3")
    with mock.patch("influxdb_client_3.InfluxDBClient3") as client:
        _one_row().to_target(f"influxdb3://acme:{_DELIMITED}@eu.example.org/?database=obs")

    kwargs = client.call_args.kwargs
    assert (kwargs["host"], kwargs["org"], kwargs["token"], kwargs["database"]) == (
        "http://eu.example.org:8181",
        "acme",
        _DELIMITED,
        "obs",
    )


def test_to_target_writes_cratedb_with_a_password_holding_delimiters() -> None:
    """CrateDB is handed a URL that reads back as the same host, port and password."""
    sqlalchemy = pytest.importorskip("sqlalchemy")
    pytest.importorskip("pandas")
    with mock.patch("pandas.DataFrame.to_sql") as to_sql:
        _one_row().to_target(f"crate://crate:{_DELIMITED}@localhost:4200/obs?table=readings")

    url = sqlalchemy.make_url(to_sql.call_args.kwargs["con"])
    assert (url.drivername, url.username, url.password, url.host, url.port) == (
        "crate",
        "crate",
        _DELIMITED,
        "localhost",
        4200,
    )
    assert (to_sql.call_args.kwargs["schema"], to_sql.call_args.kwargs["name"]) == ("obs", "readings")


@pytest.mark.parametrize(
    "written",
    [pytest.param(_DELIMITED, id="delimiters"), pytest.param("pa/ss", id="slash")],
)
def test_to_target_writes_sql_with_a_password_holding_delimiters(written: str) -> None:
    """SQLAlchemy is handed the password the target names, and the table is the one it names."""
    pytest.importorskip("sqlalchemy")
    pytest.importorskip("pandas")
    with mock.patch("sqlalchemy.create_engine") as create_engine, mock.patch("pandas.DataFrame.to_sql") as to_sql:
        _one_row().to_target(f"postgresql+psycopg2://scott:{written}@db/dwd?table=obs")

    url = create_engine.call_args.args[0]
    assert (url.password, url.host, url.database) == (written, "db", "dwd")
    assert to_sql.call_args.kwargs["name"] == "obs"


def test_to_target_hands_influxdb_an_encoded_token_decoded() -> None:
    """A percent-encoded token reaches InfluxDB decoded, as SQLAlchemy decodes a password."""
    pytest.importorskip("influxdb_client")
    with mock.patch("influxdb_client.InfluxDBClient") as client:
        _one_row().to_target("influxdb2://acme:Ab%2FCd%40%3D%3D@localhost/?database=dwd")

    client.assert_called_once_with(url="http://localhost:8086", org="acme", token="Ab/Cd@==")  # noqa: S106


def test_to_target_hands_sql_the_database_as_the_installed_sqlalchemy_reads_it() -> None:
    """SQLAlchemy 2.0 leaves an encoded database as written and 2.1 decodes it; neither is changed."""
    sqlalchemy = pytest.importorskip("sqlalchemy")
    pytest.importorskip("pandas")
    target = "postgresql+psycopg2://scott:tiger@db/data%20base?table=obs"
    with mock.patch("sqlalchemy.create_engine") as create_engine, mock.patch("pandas.DataFrame.to_sql"):
        _one_row().to_target(target)

    assert create_engine.call_args.args[0] == sqlalchemy.make_url(target).difference_update_query(["table"])


@pytest.mark.parametrize(
    ("target", "datetime_type"),
    [
        pytest.param(
            "mssql+pyodbc://u:p@localhost/dwd?driver=ODBC+Driver+18+for+SQL+Server&table=weather",
            "DATETIME2",
            id="mssql+pyodbc",
        ),
        pytest.param("mssql+pymssql://u:p@localhost/dwd?table=weather", "DATETIME2", id="mssql+pymssql"),
        # the control: MySQL's naive datetimes stay its own `DATETIME`
        pytest.param("mysql+pymysql://u:p@localhost/dwd?table=weather", "DATETIME", id="mysql+pymysql"),
    ],
)
def test_sql_sink_writes_sql_server_datetimes_as_naive_utc_datetime2(target: str, datetime_type: str) -> None:
    """A SQL Server table gets `DATETIME2` columns holding UTC, where it got a `timestamp` (GH-2249).

    pandas maps a zoned datetime to `TIMESTAMP(timezone=True)`, which the SQL Server dialect
    compiles to `TIMESTAMP`, SQL Server's name for `rowversion`: a row counter refusing any value
    written to it, so the first row failed. A naive one would be `DATETIME`, from 1753 only.
    No server is needed: the engine carries the target's dialect over a stand-in driver,
    `to_sql` is stubbed, and the frame and types it is handed are compiled into the
    `CREATE TABLE` that dialect would send.
    """
    sqlalchemy = pytest.importorskip("sqlalchemy")
    pd = pytest.importorskip("pandas")
    from pandas.io.sql import SQLDatabase, SQLTable  # noqa: PLC0415
    from sqlalchemy.schema import CreateTable  # noqa: PLC0415

    # 1700 is before `DATETIME`'s 1753. Midnight in Berlin in 1850 is 23:06:32 UTC the day before
    # (local mean time), so a zone dropped without converting to UTC first would show
    export = ExportMixin(
        df=pl.DataFrame(
            {
                "station_id": ["01048"],
                "timestamp": [dt.datetime(1700, 1, 1, tzinfo=ZoneInfo("UTC"))],
                "start_date": [dt.datetime(1850, 1, 1, tzinfo=ZoneInfo("Europe/Berlin"))],
                "end_date": pl.Series([None], dtype=pl.Datetime("us", "UTC")),
                "value": [1.0],
            }
        )
    )
    create_engine = sqlalchemy.create_engine
    engines = []
    handed = []

    def engine_for(url: object, **kwargs: object) -> object:
        # the target's real dialect, with a stand-in driver: nothing connects before `to_sql`.
        # pyodbc's dialect reads the driver's version as it is built
        driver = mock.MagicMock(version="5.2.0", __version__="2.3.13")
        engines.append(create_engine(url, module=driver, **kwargs))
        return engines[-1]

    def to_sql(frame: object, **kwargs: object) -> None:
        handed.append((frame, kwargs["dtype"]))

    with (
        mock.patch("sqlalchemy.create_engine", side_effect=engine_for),
        mock.patch.object(pd.DataFrame, "to_sql", autospec=True, side_effect=to_sql),
    ):
        export.to_target(target)

    ((engine,), ((frame, dtype),)) = engines, handed
    with SQLDatabase(create_engine("sqlite://")) as database:
        table = SQLTable("weather", database, frame=frame, index=False, dtype=dtype).table
        ddl = str(CreateTable(table).compile(dialect=engine.dialect))
    assert f"timestamp {datetime_type}" in ddl
    assert f"start_date {datetime_type}" in ddl
    assert f"end_date {datetime_type}" in ddl
    assert "TIMESTAMP" not in ddl
    assert frame["timestamp"].tolist() == [pd.Timestamp("1700-01-01 00:00:00")]
    assert frame["start_date"].tolist() == [pd.Timestamp("1849-12-31 23:06:32")]
    assert frame["end_date"].isna().tolist() == [True]


def _two_dataset_stations_result() -> StationsResult:
    """Build a stations result of one station in two daily datasets, one row per dataset.

    As DWD observation lists it: a stations frame holds one row per resolution, dataset and
    station, and a station in two datasets gets two rows.
    """
    station = {
        "resolution": "daily",
        "station_id": "01048",
        "start_date": None,
        "end_date": None,
        "latitude": 51.1,
        "longitude": 13.8,
        "elevation": 228.0,
        "name": "Dresden-Klotzsche",
        "region": "Sachsen",
    }
    df = pl.DataFrame(
        [{**station, "dataset": "climate_summary"}, {**station, "dataset": "precipitation_more"}],
        schema={
            "resolution": pl.String,
            "dataset": pl.String,
            "station_id": pl.String,
            "start_date": pl.Datetime(time_zone="UTC"),
            "end_date": pl.Datetime(time_zone="UTC"),
            "latitude": pl.Float64,
            "longitude": pl.Float64,
            "elevation": pl.Float64,
            "name": pl.String,
            "region": pl.String,
        },
        orient="row",
    )
    return StationsResult(df=df, df_all=df, stations_filter=StationsFilter.ALL, stations=None)


def _values_result(stations: StationsResult, rows: list[dict]) -> ValuesResult:
    """Build a values result of hand-written rows, its metadata columns Enum as a real one's are."""
    df_values = pl.DataFrame(rows, schema_overrides={"timestamp": pl.Datetime(time_zone="UTC")}, orient="row")
    df_values = TimeseriesValues._cast_metadata_to_enum(df_values)  # noqa: SLF001
    return ValuesResult(stations=stations, values=None, df=df_values)


def test_values_to_ogc_feature_collection_gives_each_dataset_its_own_values() -> None:
    """A station in two datasets gets one feature per dataset, each with that dataset's values only.

    Both features carried the values of both datasets, so every value appeared twice, once under
    a feature whose dataset did not match it.
    """
    timestamp = dt.datetime(2026, 1, 1, tzinfo=ZoneInfo("UTC"))
    value = {"station_id": "01048", "resolution": "daily", "timestamp": timestamp, "quality": 1.0}
    result = _values_result(
        _two_dataset_stations_result(),
        [
            {**value, "dataset": "climate_summary", "parameter": "temperature_air_mean_2m", "value": 1.0},
            {**value, "dataset": "precipitation_more", "parameter": "precipitation_height", "value": 2.0},
        ],
    )
    features = json.loads(result.to_geojson())["data"]["features"]
    assert [
        (feature["properties"]["dataset"], [(v["dataset"], v["value"]) for v in feature["values"]])
        for feature in features
    ] == [
        ("climate_summary", [("climate_summary", 1.0)]),
        ("precipitation_more", [("precipitation_more", 2.0)]),
    ]
    # a feature's values still leave out the station id its properties carry
    assert all("station_id" not in v for feature in features for v in feature["values"])


def test_values_to_ogc_feature_collection_leaves_out_a_dataset_without_values() -> None:
    """A dataset the station returned no values for gets no feature, nor the other dataset's values."""
    result = _values_result(
        _two_dataset_stations_result(),
        [
            {
                "station_id": "01048",
                "resolution": "daily",
                "dataset": "climate_summary",
                "parameter": "temperature_air_mean_2m",
                "timestamp": dt.datetime(2026, 1, 1, tzinfo=ZoneInfo("UTC")),
                "value": 1.0,
                "quality": 1.0,
            },
        ],
    )
    features = json.loads(result.to_geojson())["data"]["features"]
    assert [(feature["properties"]["dataset"], len(feature["values"])) for feature in features] == [
        ("climate_summary", 1),
    ]


def test_values_to_ogc_feature_collection_wide_rows_spanning_datasets() -> None:
    """A wide row spanning two datasets of one resolution, and so naming none, goes to one feature.

    Such a row holds the columns of each dataset, and it went, whole, to the feature of each of
    them, so every value appeared once per dataset (GH-2274). The station gets one feature for
    the resolution, with a null dataset as its rows carry.
    """
    result = _values_result(
        _two_dataset_stations_result(),
        [
            {
                "station_id": "01048",
                "resolution": "daily",
                "dataset": None,
                "timestamp": dt.datetime(2026, 1, 1, tzinfo=ZoneInfo("UTC")),
                "climate_summary_temperature_air_mean_2m": 1.0,
                "precipitation_more_precipitation_height": 2.0,
            },
        ],
    )
    features = json.loads(result.to_geojson())["data"]["features"]
    row = {
        "resolution": "daily",
        "dataset": None,
        "timestamp": "2026-01-01T00:00:00.000000+00:00",
        "climate_summary_temperature_air_mean_2m": 1.0,
        "precipitation_more_precipitation_height": 2.0,
    }
    assert [(feature["properties"]["dataset"], feature["values"]) for feature in features] == [(None, [row])]
    # position, name and the other station columns come from the station's rows
    assert features[0]["geometry"] == {"type": "Point", "coordinates": [13.8, 51.1, 228.0]}
    assert features[0]["properties"] == {
        "resolution": "daily",
        "dataset": None,
        "id": "01048",
        "name": "Dresden-Klotzsche",
        "region": "Sachsen",
        "start_date": None,
        "end_date": None,
    }


def _unlocated_stations_result() -> StationsResult:
    """Build a stations result of one located station and two without a full position.

    "10115" is a postcode, which DWD derived's climate_correction_factor lists as a station with
    no latitude, longitude or elevation; "half" has a latitude but no longitude.
    """
    station = {"resolution": "monthly", "dataset": "climate_correction_factor", "start_date": None, "end_date": None}
    df = pl.DataFrame(
        [
            {**station, "station_id": "located", "latitude": 50.0, "longitude": 8.0, "elevation": None, "name": "A"},
            {**station, "station_id": "10115", "latitude": None, "longitude": None, "elevation": None, "name": None},
            {**station, "station_id": "half", "latitude": 51.0, "longitude": None, "elevation": 10.0, "name": None},
        ],
        schema={
            "resolution": pl.String,
            "dataset": pl.String,
            "station_id": pl.String,
            "start_date": pl.Datetime(time_zone="UTC"),
            "end_date": pl.Datetime(time_zone="UTC"),
            "latitude": pl.Float64,
            "longitude": pl.Float64,
            "elevation": pl.Float64,
            "name": pl.String,
        },
        orient="row",
    ).with_columns(region=pl.lit(None, dtype=pl.String))
    return StationsResult(df=df, df_all=df, stations_filter=StationsFilter.ALL, stations=None)


# per station id: the feature's geometry, null where the station has no position
_UNLOCATED_GEOMETRIES = {
    "located": {"type": "Point", "coordinates": [8.0, 50.0]},
    "10115": None,
    "half": None,
}


def test_stations_to_ogc_feature_collection_without_position() -> None:
    """A station without a latitude or longitude gets a null geometry, not a Point of null coordinates.

    RFC 7946 3.1.1 makes a position two or more numbers, and 3.2 writes an unlocated feature with a
    null geometry.
    """
    features = json.loads(_unlocated_stations_result().to_geojson())["data"]["features"]
    assert {feature["properties"]["id"]: feature["geometry"] for feature in features} == _UNLOCATED_GEOMETRIES


def test_values_to_ogc_feature_collection_without_position() -> None:
    """The values variant writes a station without a position with a null geometry too."""
    result = _values_result(
        _unlocated_stations_result(),
        [
            {
                "station_id": station_id,
                "resolution": "monthly",
                "dataset": "climate_correction_factor",
                "parameter": "climate_correction_factor",
                "timestamp": dt.datetime(2026, 1, 1, tzinfo=ZoneInfo("UTC")),
                "value": 1.0,
                "quality": None,
            }
            for station_id in _UNLOCATED_GEOMETRIES
        ],
    )
    features = json.loads(result.to_geojson())["data"]["features"]
    assert {feature["properties"]["id"]: feature["geometry"] for feature in features} == _UNLOCATED_GEOMETRIES


def test_values_to_ogc_feature_collection_merged_datasets_span_their_dates() -> None:
    """A merged resolution's feature spans its datasets' dates, per station; another resolution is kept.

    Each station gets one daily feature, from the earliest start to the latest end of its two daily
    datasets, a null date not counting. The hourly resolution holds one dataset, so the wide shape
    names it on its rows and its feature keeps that name and its own dates (GH-2274).
    """

    def utc(year: int, month: int = 1) -> dt.datetime:
        return dt.datetime(year, month, 1, tzinfo=ZoneInfo("UTC"))

    stations = pl.DataFrame(
        [
            ("daily", "climate_summary", "01048", utc(1950), utc(2026)),
            ("daily", "precipitation_more", "01048", utc(1940), utc(2025, 6)),
            ("daily", "climate_summary", "00011", utc(2000), utc(2020)),
            ("daily", "precipitation_more", "00011", None, utc(2021)),
            ("hourly", "temperature_air", "01048", utc(1990), utc(2026, 2)),
        ],
        schema={
            "resolution": pl.String,
            "dataset": pl.String,
            "station_id": pl.String,
            "start_date": pl.Datetime(time_zone="UTC"),
            "end_date": pl.Datetime(time_zone="UTC"),
        },
        orient="row",
    ).with_columns(
        latitude=pl.lit(51.1),
        longitude=pl.lit(13.8),
        elevation=pl.lit(None, dtype=pl.Float64),
        name=pl.col("station_id"),
        region=pl.lit(None, dtype=pl.String),
    )
    wide = {
        "climate_summary_temperature_air_mean_2m": 1.0,
        "precipitation_more_precipitation_height": 2.0,
        "temperature_air_temperature_air_mean_2m": None,
    }
    result = _values_result(
        StationsResult(df=stations, df_all=stations, stations_filter=StationsFilter.ALL, stations=None),
        [
            {"station_id": "01048", "resolution": "daily", "dataset": None, "timestamp": utc(2025), **wide},
            {"station_id": "00011", "resolution": "daily", "dataset": None, "timestamp": utc(2019), **wide},
            {
                "station_id": "01048",
                "resolution": "hourly",
                "dataset": "temperature_air",
                "timestamp": utc(2025),
                **wide,
                "temperature_air_temperature_air_mean_2m": 3.0,
            },
        ],
    )
    features = json.loads(result.to_geojson())["data"]["features"]
    assert [
        (
            feature["properties"]["resolution"],
            feature["properties"]["dataset"],
            feature["properties"]["id"],
            feature["properties"]["start_date"],
            feature["properties"]["end_date"],
            [value["timestamp"][:4] for value in feature["values"]],
        )
        for feature in features
    ] == [
        ("daily", None, "01048", "1940-01-01T00:00:00.000000+00:00", "2026-01-01T00:00:00.000000+00:00", ["2025"]),
        ("daily", None, "00011", "2000-01-01T00:00:00.000000+00:00", "2021-01-01T00:00:00.000000+00:00", ["2019"]),
        (
            "hourly",
            "temperature_air",
            "01048",
            "1990-01-01T00:00:00.000000+00:00",
            "2026-02-01T00:00:00.000000+00:00",
            ["2025"],
        ),
    ]


@pytest.mark.parametrize(
    ("target", "host"),
    [
        # the bare host went to https on 443 whatever the target named
        pytest.param("influxdb3://acme:tok@localhost:9181/?database=dwd", "http://localhost:9181", id="port"),
        pytest.param(
            "influxdb3s://acme:tok@eu.example.org:8443/?database=dwd", "https://eu.example.org:8443", id="ssl"
        ),
        pytest.param("influxdb3://acme:tok@[::1]:9181/?database=dwd", "http://[::1]:9181", id="ipv6"),
        # with no port: the 8181 an InfluxDB 3 Core listens on over http, 443 over https
        pytest.param("influxdb3://acme:tok@localhost/?database=dwd", "http://localhost:8181", id="http-default"),
        pytest.param(
            "influxdb3s://acme:tok@eu.example.org/?database=dwd", "https://eu.example.org:443", id="ssl-default"
        ),
    ],
)
def test_to_target_hands_influxdb3_the_scheme_host_and_port_the_target_names(target: str, host: str) -> None:
    """InfluxDB 3 is handed one URL: http or https by the protocol, the target's port, IPv6 in brackets."""
    pytest.importorskip("influxdb_client_3")
    with mock.patch("influxdb_client_3.InfluxDBClient3") as client:
        _one_row().to_target(target)

    assert client.call_args.kwargs["host"] == host


@pytest.mark.parametrize(
    ("target", "url"),
    [
        # the bare `::1` made `http://::1:8086`, which has no valid host
        pytest.param("influxdb2://acme:tok@[::1]:8086/?database=dwd", "http://[::1]:8086", id="ipv6"),
        pytest.param("influxdb2s://acme:tok@[2001:db8::1]/?database=dwd", "https://[2001:db8::1]:8086", id="ipv6-ssl"),
        pytest.param("influxdb2://acme:tok@localhost:9999/?database=dwd", "http://localhost:9999", id="port"),
    ],
)
def test_to_target_hands_influxdb2_the_scheme_host_and_port_the_target_names(target: str, url: str) -> None:
    """InfluxDB 2 is handed one URL: http or https by the protocol, the target's port, IPv6 in brackets."""
    pytest.importorskip("influxdb_client")
    with mock.patch("influxdb_client.InfluxDBClient") as client:
        _one_row().to_target(target)

    assert client.call_args.kwargs["url"] == url


def test_to_target_leaves_influxdb3_a_target_with_no_host_to_refuse() -> None:
    """No host is handed on as none, which the client refuses by name, not as a URL to `None`."""
    pytest.importorskip("influxdb_client_3")
    with mock.patch("influxdb_client_3.InfluxDBClient3") as client:
        _one_row().to_target("influxdb3://acme:tok@/?database=dwd")

    assert client.call_args.kwargs["host"] is None


@pytest.mark.parametrize(
    ("target", "host"),
    [
        # the bare `::1` made the client's base URL `http://::1:8086`, which has no valid host
        pytest.param("influxdb://root:pw@[::1]:8086/?database=dwd", "[::1]", id="ipv6"),
        pytest.param("influxdbs://root:pw@[2001:db8::1]/?database=dwd", "[2001:db8::1]", id="ipv6-ssl"),
        pytest.param("influxdb://root:pw@localhost:8086/?database=dwd", "localhost", id="name"),
        pytest.param("influxdb://root:pw@127.0.0.1:8086/?database=dwd", "127.0.0.1", id="ipv4"),
    ],
)
def test_to_target_hands_influxdb1_an_ipv6_host_in_brackets(target: str, host: str) -> None:
    """InfluxDB 1 is handed an IPv6 host in the brackets `ConnectionString` reads it out of."""
    pytest.importorskip("influxdb")
    with mock.patch("influxdb.InfluxDBClient") as client:
        _one_row().to_target(target)

    assert client.call_args.kwargs["host"] == host


@pytest.mark.parametrize(
    ("target", "baseurl"),
    [
        pytest.param("influxdb://root:pw@[::1]:8086/?database=dwd", "http://[::1]:8086", id="ipv6"),
        pytest.param("influxdbs://root:pw@[2001:db8::1]/?database=dwd", "https://[2001:db8::1]:8086", id="ipv6-ssl"),
    ],
)
def test_to_target_gives_the_influxdb1_client_a_valid_base_url_for_an_ipv6_host(target: str, baseurl: str) -> None:
    """The real InfluxDB 1 client, handed what the sink hands it, builds a URL `requests` can send to."""
    influxdb = pytest.importorskip("influxdb")
    requests = pytest.importorskip("requests")
    clients = []

    class _Offline(influxdb.InfluxDBClient):
        """The real client, recorded, with the two calls the sink makes kept off the network."""

        def __init__(self, *args: object, **kwargs: object) -> None:
            super().__init__(*args, **kwargs)
            clients.append(self)

        def create_database(self, dbname: str) -> None:
            pass

        def write_points(self, *args: object, **kwargs: object) -> None:
            pass

    with mock.patch("influxdb.InfluxDBClient", _Offline):
        _one_row().to_target(target)

    (client,) = clients
    assert client._baseurl == baseurl  # noqa: SLF001
    # `requests` refused the unbracketed `http://::1:8086` as an InvalidURL before sending anything
    assert requests.Request("GET", f"{baseurl}/ping").prepare().url == f"{baseurl}/ping"


def _plot_of(result: ValuesResult) -> tuple[list, list[tuple]]:
    """Read what a values plot draws: its facets' labels, and each trace's points with its facet's.

    Both in the order the figure holds them, which is the order they are laid out in.
    """
    figure = result.to_plot()

    def label(axis: str) -> str:
        # a facet's label sits at the middle of its y axis, in paper coordinates
        bottom, top = figure.layout[axis.replace("y", "yaxis")].domain
        (text,) = (a.text for a in figure.layout.annotations if math.isclose(a.y, (bottom + top) / 2))
        return text

    return (
        [annotation.text for annotation in figure.layout.annotations],
        [(label(trace.yaxis), trace.name, tuple(trace.x), tuple(trace.y)) for trace in figure.data],
    )


@pytest.mark.parametrize(
    ("settings_kwargs", "parameters", "names"),
    [
        pytest.param(
            {},
            [
                "hourly/temperature_air/temperature_air_mean_2m",
                "daily/more_precip/precipitation_amount",
                "daily/kl/precipitation_amount",
                "daily/kl/temperature_air_mean_2m",
            ],
            ["temperature_air_mean_2m", "precipitation_amount", "precipitation_amount", "temperature_air_mean_2m"],
            id="two-datasets-merged-in-one-resolution",
        ),
        pytest.param(
            {"ts_humanize": False},
            ["daily/kl/temperature_air_mean_2m", "hourly/temperature_air/temperature_air_mean_2m"],
            ["tmk", "tt_tu"],
            id="original-names-two-resolutions",
        ),
        pytest.param(
            {},
            ["daily/kl/temperature_air_mean_2m", "daily/kl/precipitation_amount"],
            ["temperature_air_mean_2m", "precipitation_amount"],
            id="one-dataset",
        ),
        pytest.param(
            {"ts_humanize": False},
            ["hourly/wind/wind_speed", "hourly/wind_extreme/wind_gust_max"],
            ["f", "fx_911"],
            id="one-dataset-name-beginning-another",
        ),
    ],
)
def test_values_plot_of_a_wide_frame_draws_what_the_long_frame_does(
    settings_kwargs: dict,
    parameters: list[str],
    names: list[str],
) -> None:
    """A wide result plots as the long one does, rather than failing on the `parameter` column.

    The plot read the parameter name off a `parameter` column, which the wide shape has none of,
    so every image format of a wide result raised `ColumnNotFoundError` (GH-2330).
    """
    pytest.importorskip("plotly")
    request = DwdObservationRequest(parameters=parameters, settings=Settings(**settings_kwargs))
    stations = StationsResult(
        stations=request,
        df=pl.DataFrame(),
        df_all=pl.DataFrame(),
        stations_filter=StationsFilter.ALL,
    )
    values = stations.values
    series = [
        (parameter.dataset.resolution.name, parameter.dataset.name, name)
        for parameter, name in zip(request.parameters, names, strict=True)
    ]
    rows = []
    for station_id in ("01048", "04411"):
        for resolution, dataset, name in series:
            # the first station has none of the series that sorts first, so it lays out its facets
            # and takes its colour in a different order than a sort of all the rows would
            if station_id == "01048" and (resolution, dataset, name) == min(series):
                continue
            timestamps = (
                [dt.datetime(2020, 1, 1, hour, tzinfo=ZoneInfo("UTC")) for hour in (0, 1)]
                if resolution == "hourly"
                else [dt.datetime(2020, 1, day, tzinfo=ZoneInfo("UTC")) for day in (1, 2)]
            )
            rows.extend(
                {
                    "station_id": station_id,
                    "resolution": resolution,
                    "dataset": dataset,
                    "parameter": name,
                    "timestamp": timestamp,
                    "value": float(len(rows) + index),
                    "quality": 10.0,
                }
                for index, timestamp in enumerate(timestamps)
            )
    # one reading of the last series missing, which the wide shape writes as a null where another
    # series of its resolution has a reading at that timestamp
    rows.pop()
    df_collected = pl.DataFrame(rows, schema=TimeseriesValues._long_fields)  # noqa: SLF001
    # shaped and sorted one station at a time and then put together, as a request does
    stations_collected = [df for _, df in df_collected.group_by("station_id", maintain_order=True)]
    df_long = pl.concat(df.sort("resolution", "dataset", "parameter", "timestamp") for df in stations_collected)
    # diagonally, as a station that has none of a series has no column for it
    df_wide = pl.concat(
        [values._widen_df(df).sort("resolution", "dataset", "timestamp") for df in stations_collected],  # noqa: SLF001
        how="diagonal",
    )
    long = ValuesResult(stations=stations, values=values, df=values._cast_metadata_to_enum(df_long))  # noqa: SLF001
    wide = ValuesResult(stations=stations, values=values, df=values._cast_metadata_to_enum(df_wide))  # noqa: SLF001
    assert "parameter" not in df_wide.columns
    assert _plot_of(wide) == _plot_of(long)


def test_values_plot_of_an_empty_wide_frame_is_an_empty_figure() -> None:
    """A wide result with no rows plots as an empty long one does, as a figure with nothing drawn."""
    pytest.importorskip("plotly")
    request = DwdObservationRequest(parameters=["daily/kl/temperature_air_mean_2m"])
    stations = StationsResult(
        stations=request,
        df=pl.DataFrame(),
        df_all=pl.DataFrame(),
        stations_filter=StationsFilter.ALL,
    )
    df = stations.values._widen_df(pl.DataFrame(schema=TimeseriesValues._long_fields))  # noqa: SLF001
    assert ValuesResult(stations=stations, values=stations.values, df=df).to_plot().data == ()
