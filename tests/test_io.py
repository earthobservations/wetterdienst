# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for export of timeseries data."""

import datetime as dt
import json
import sqlite3
from pathlib import Path
from unittest import mock
from zoneinfo import ZoneInfo

import polars as pl
import pytest

from tests.conftest import IS_CI, IS_WINDOWS
from wetterdienst import Settings
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
        "date",
        "wind_gust_max",
        "qn_wind_gust_max",
        "wind_speed",
        "qn_wind_speed",
        "precipitation_height",
        "qn_precipitation_height",
        "precipitation_form",
        "qn_precipitation_form",
        "sunshine_duration",
        "qn_sunshine_duration",
        "snow_depth",
        "qn_snow_depth",
        "cloud_cover_total",
        "qn_cloud_cover_total",
        "pressure_vapor",
        "qn_pressure_vapor",
        "pressure_air_site",
        "qn_pressure_air_site",
        "temperature_air_mean_2m",
        "qn_temperature_air_mean_2m",
        "humidity",
        "qn_humidity",
        "temperature_air_max_2m",
        "qn_temperature_air_max_2m",
        "temperature_air_min_2m",
        "qn_temperature_air_min_2m",
        "temperature_air_min_0_05m",
        "qn_temperature_air_min_0_05m",
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
                "height": 645.0,
                "latitude": 48.8049,
                "longitude": 13.5528,
                "name": "Freyung vorm Wald",
                "state": "Bayern",
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
                "date": dt.datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC")),
                "value": 1.3,
                "quality": None,
            },
            {
                "station_id": "01048",
                "resolution": "daily",
                "dataset": "climate_summary",
                "parameter": "temperature_air_max_2m",
                "date": dt.datetime(2019, 12, 1, tzinfo=ZoneInfo("UTC")),
                "value": 1.0,
                "quality": None,
            },
            {
                "station_id": "01048",
                "resolution": "daily",
                "dataset": "climate_summary",
                "parameter": "temperature_air_max_2m",
                "date": dt.datetime(2019, 12, 28, tzinfo=ZoneInfo("UTC")),
                "value": 1.3,
                "quality": None,
            },
            {
                "station_id": "01048",
                "resolution": "daily",
                "dataset": "climate_summary",
                "parameter": "temperature_air_max_2m",
                "date": dt.datetime(2020, 1, 1, tzinfo=ZoneInfo("UTC")),
                "value": 2.0,
                "quality": None,
            },
            {
                "station_id": "01048",
                "resolution": "daily",
                "dataset": "climate_summary",
                "parameter": "temperature_air_max_2m",
                "date": dt.datetime(2021, 1, 1, tzinfo=ZoneInfo("UTC")),
                "value": 3.0,
                "quality": None,
            },
            {
                "station_id": "01048",
                "resolution": "daily",
                "dataset": "climate_summary",
                "parameter": "temperature_air_max_2m",
                "date": dt.datetime(2022, 1, 1, tzinfo=ZoneInfo("UTC")),
                "value": 4.0,
                "quality": None,
            },
        ],
        schema={
            "station_id": pl.String,
            "resolution": pl.String,
            "dataset": pl.String,
            "parameter": pl.String,
            "date": pl.Datetime(time_zone="UTC"),
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
                "date": dt.datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC")),
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
            "date": pl.Datetime(time_zone="UTC"),
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
                "date": dt.datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC")),
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
            "date": pl.Datetime(time_zone="UTC"),
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
            "height": 645.0,
            "latitude": 48.8049,
            "longitude": 13.5528,
            "name": "Freyung vorm Wald",
            "state": "Bayern",
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
            "state": "Bayern",
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
    assert lines[0] == "resolution,dataset,station_id,start_date,end_date,height,latitude,longitude,name,state"
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
            "date": "2019-01-01T00:00:00.000000+00:00",
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
            "state": "Bayern",
            "start_date": "1957-05-01T00:00:00.000000+00:00",
            "end_date": "1995-11-30T00:00:00.000000+00:00",
        },
        "type": "Feature",
        "values": [
            {
                "resolution": "daily",
                "dataset": "climate_summary",
                "parameter": "temperature_air_max_2m",
                "date": "2019-01-01T00:00:00.000000+00:00",
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
        "date": "2019-01-01T00:00:00.000000+00:00",
        "value": 1.3,
        "quality": None,
    }


def test_values_format_csv(df_values: pl.DataFrame) -> None:
    """Test export of DataFrame to csv."""
    output = ValuesResult(stations=None, values=None, df=df_values).to_csv().strip()
    lines = output.split("\n")
    assert lines[0] == "station_id,resolution,dataset,parameter,date,value,quality"
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
            "date": "2019-01-01T00:00:00.000000+00:00",
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
                "height": 645.0,
                "name": "Freyung vorm Wald",
                "state": "Bayern",
            },
        ],
        "type": "Feature",
        "values": [
            {
                "station_id": "abc",
                "resolution": "daily",
                "dataset": "climate_summary",
                "parameter": "temperature_air_max_2m",
                "date": "2019-01-01T00:00:00.000000+00:00",
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
            "date": "2019-01-01T00:00:00.000000+00:00",
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
                "height": 645.0,
                "name": "Freyung vorm Wald",
                "state": "Bayern",
            },
        ],
        "type": "Feature",
        "values": [
            {
                "station_id": "abc",
                "resolution": "daily",
                "dataset": "climate_summary",
                "parameter": "temperature_air_max_2m",
                "date": "2019-01-01T00:00:00.000000+00:00",
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
            "date": [dt.datetime(2020, 1, 1, tzinfo=ZoneInfo("UTC"))],
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
            "date": [dt.datetime(2020, 1, 1, tzinfo=ZoneInfo("UTC"))] * 2,
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
            "date": [dt.datetime(2019, 12, 28, hour, tzinfo=ZoneInfo("UTC")) for hour in range(24)]
            + [dt.datetime(2019, 12, 15, tzinfo=ZoneInfo("UTC")), dt.datetime(2020, 1, 15, tzinfo=ZoneInfo("UTC"))],
            "value": [float(hour) for hour in range(24)] + [99.0, 111.0],
        },
        schema={"date": pl.Datetime(time_zone="UTC"), "value": pl.Float64},
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
    """Station metadata can be filtered by SQL, which is what the CLI offers it for.

    `--sql "state='Sachsen'"` is documented as a filter on station metadata and reaches
    `filter_by_sql`, which stripped the time zone off a `date` column -- a stations frame has
    `start_date` and `end_date` and no `date`, so the documented filter always raised
    `ColumnNotFoundError`.
    """
    df = ExportMixin(df=df_stations).filter_by_sql("state='Bayern'")
    assert df.get_column("station_id").to_list() == ["01048"]
    # the timestamps keep the zone they came with
    assert df.schema["start_date"].time_zone == "UTC"
    assert ExportMixin(df=df_stations).filter_by_sql("state='Sachsen'").is_empty()


@pytest.mark.parametrize("extension", ["csv", "json", "jsonl", "xlsx", "parquet", "feather"])
def test_export_file_targets_take_a_stations_frame(
    df_stations: pl.DataFrame,
    tmp_path: Path,
    extension: str,
) -> None:
    """Every flat file target takes a frame without a `date` column."""
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
    assert read.get_column("date").to_list()[0].startswith("2019-01-01T00:00:00")


def test_export_netcdf(df_interpolated_values: pl.DataFrame, tmp_path: Path) -> None:
    """NetCDF is written through xarray, with CF timestamps and the station ids as one field."""
    xarray = pytest.importorskip("xarray")
    pytest.importorskip("h5netcdf")
    filename = tmp_path.joinpath("values.nc")
    ExportMixin(df=df_interpolated_values).to_target(f"file://{filename}")
    dataset = xarray.open_dataset(filename, group="climate_summary")
    assert str(dataset["date"].values[0]).startswith("2019-01-01T00:00:00")
    assert dataset["taken_station_ids"].values[0] == "01048,1050"


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
    with pytest.raises(KeyError) as exec_info:
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
        "date",
        "wind_gust_max",
        "qn_wind_gust_max",
        "wind_speed",
        "qn_wind_speed",
        "precipitation_height",
        "qn_precipitation_height",
        "precipitation_form",
        "qn_precipitation_form",
        "sunshine_duration",
        "qn_sunshine_duration",
        "snow_depth",
        "qn_snow_depth",
        "cloud_cover_total",
        "qn_cloud_cover_total",
        "pressure_vapor",
        "qn_pressure_vapor",
        "pressure_air_site",
        "qn_pressure_air_site",
        "temperature_air_mean_2m",
        "qn_temperature_air_mean_2m",
        "humidity",
        "qn_humidity",
        "temperature_air_max_2m",
        "qn_temperature_air_max_2m",
        "temperature_air_min_2m",
        "qn_temperature_air_min_2m",
        "temperature_air_min_0_05m",
        "qn_temperature_air_min_0_05m",
    ]
    # Validate number of records.
    assert len(df) == 366
    first_record = df.head(1).to_dicts()[0]
    assert first_record == {
        "station_id": "01048",
        "resolution": "daily",
        "dataset": "climate_summary",
        "date": "2019-01-01T00:00:00.000000+00:00",
        "wind_gust_max": 19.9,
        "qn_wind_gust_max": 10,
        "wind_speed": 8.5,
        "qn_wind_speed": 10,
        "precipitation_height": 0.9,
        "qn_precipitation_height": 10,
        "precipitation_form": 8.0,
        "qn_precipitation_form": 10,
        "sunshine_duration": 0.0,
        "qn_sunshine_duration": 10,
        "snow_depth": 0,
        "qn_snow_depth": 10,
        "cloud_cover_total": 7.4,
        "qn_cloud_cover_total": 10,
        "pressure_vapor": 7.9,
        "qn_pressure_vapor": 10,
        "pressure_air_site": 991.9,
        "qn_pressure_air_site": 10,
        "temperature_air_mean_2m": 5.9,
        "qn_temperature_air_mean_2m": 10,
        "humidity": 84,
        "qn_humidity": 10,
        "temperature_air_max_2m": 7.5,
        "qn_temperature_air_max_2m": 10,
        "temperature_air_min_2m": 2.0,
        "qn_temperature_air_min_2m": 10,
        "temperature_air_min_0_05m": 1.5,
        "qn_temperature_air_min_0_05m": 10,
    }
    last_record = df.tail(1).to_dicts()[0]
    assert last_record == {
        "station_id": "01048",
        "resolution": "daily",
        "dataset": "climate_summary",
        "date": "2020-01-01T00:00:00.000000+00:00",
        "wind_gust_max": 6.9,
        "qn_wind_gust_max": 10,
        "wind_speed": 3.2,
        "qn_wind_speed": 10,
        "precipitation_height": 0.0,
        "qn_precipitation_height": 10,
        "precipitation_form": 0,
        "qn_precipitation_form": 10,
        "sunshine_duration": 3.9,
        "qn_sunshine_duration": 10,
        "snow_depth": 0,
        "qn_snow_depth": 10,
        "cloud_cover_total": 4.2,
        "qn_cloud_cover_total": 10,
        "pressure_vapor": 5.7,
        "qn_pressure_vapor": 10,
        "pressure_air_site": 1005.1,
        "qn_pressure_air_site": 10,
        "temperature_air_mean_2m": 2.4,
        "qn_temperature_air_mean_2m": 10,
        "humidity": 79,
        "qn_humidity": 10,
        "temperature_air_max_2m": 5.6,
        "qn_temperature_air_max_2m": 10,
        "temperature_air_min_2m": -2.8,
        "qn_temperature_air_min_2m": 10,
        "temperature_air_min_0_05m": -4.6,
        "qn_temperature_air_min_0_05m": 10,
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
    assert data["date"][0] == dt.datetime(2019, 1, 1, 0, 0, tzinfo=ZoneInfo("UTC"))
    assert data["temperature_air_min_0_05m"][0] == 1.5
    assert data["date"][-1] == dt.datetime(2020, 1, 1, 0, 0, tzinfo=ZoneInfo("UTC"))
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
    assert dt.datetime.fromtimestamp(int(data["date"][0]) / 1e9, tz=ZoneInfo("UTC")) == dt.datetime(
        2019,
        1,
        1,
        0,
        0,
        tzinfo=ZoneInfo("UTC"),
    )
    assert data["temperature_air_min_0_05m"][0] == 1.5
    assert dt.datetime.fromtimestamp(int(data["date"][-1]) / 1e9, tz=ZoneInfo("UTC")) == dt.datetime(
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
    assert "climate_summary_precipitation_height" in columns
    assert "precipitation_more_precipitation_height" in columns


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
    assert data["date"][0] == dt.datetime(2019, 1, 1, 0, 0, tzinfo=ZoneInfo("UTC"))
    assert data["temperature_air_min_0_05m"][0] == 1.5
    assert data["date"][-1] == dt.datetime(2020, 1, 1, 0, 0, tzinfo=ZoneInfo("UTC"))
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
            date = '1939-07-26'
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
            "humidity": 84.0,
            "precipitation_form": 8.0,
            "precipitation_height": 0.9,
            "pressure_air_site": 991.9,
            "pressure_vapor": 7.9,
            "qn_cloud_cover_total": 10.0,
            "qn_humidity": 10.0,
            "qn_precipitation_form": 10.0,
            "qn_precipitation_height": 10.0,
            "qn_pressure_air_site": 10.0,
            "qn_pressure_vapor": 10.0,
            "qn_snow_depth": 10.0,
            "qn_sunshine_duration": 10.0,
            "qn_temperature_air_max_2m": 10.0,
            "qn_temperature_air_mean_2m": 10.0,
            "qn_temperature_air_min_0_05m": 10.0,
            "qn_temperature_air_min_2m": 10.0,
            "qn_wind_gust_max": 10.0,
            "qn_wind_speed": 10.0,
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
            "humidity": 84.0,
            "precipitation_form": 8.0,
            "precipitation_height": 0.9,
            "pressure_air_site": 991.9,
            "pressure_vapor": 7.9,
            "qn_cloud_cover_total": 10.0,
            "qn_humidity": 10.0,
            "qn_precipitation_form": 10.0,
            "qn_precipitation_height": 10.0,
            "qn_pressure_air_site": 10.0,
            "qn_pressure_vapor": 10.0,
            "qn_snow_depth": 10.0,
            "qn_sunshine_duration": 10.0,
            "qn_temperature_air_max_2m": 10.0,
            "qn_temperature_air_mean_2m": 10.0,
            "qn_temperature_air_min_0_05m": 10.0,
            "qn_temperature_air_min_2m": 10.0,
            "qn_wind_gust_max": 10.0,
            "qn_wind_speed": 10.0,
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
            host="localhost",
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
            "humidity": 84.0,
            "precipitation_form": 8.0,
            "precipitation_height": 0.9,
            "pressure_air_site": 991.9,
            "pressure_vapor": 7.9,
            "qn_cloud_cover_total": 10.0,
            "qn_humidity": 10.0,
            "qn_precipitation_form": 10.0,
            "qn_precipitation_height": 10.0,
            "qn_pressure_air_site": 10.0,
            "qn_pressure_vapor": 10.0,
            "qn_snow_depth": 10.0,
            "qn_sunshine_duration": 10.0,
            "qn_temperature_air_max_2m": 10.0,
            "qn_temperature_air_mean_2m": 10.0,
            "qn_temperature_air_min_0_05m": 10.0,
            "qn_temperature_air_min_2m": 10.0,
            "qn_wind_gust_max": 10.0,
            "qn_wind_speed": 10.0,
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
            host="localhost",
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


# test for to_target with if_exists parameter, use duckdb for simplicity
def test_export_duckdb_if_exists_fail(
    tmp_path: Path,
) -> None:
    """Test export of DataFrame to duckdb with if_exists parameter."""
    pytest.importorskip("duckdb")

    request = DwdObservationRequest(
        parameters=[("daily", "climate_summary")],
        periods=Period.HISTORICAL,
    ).filter_by_station_id(station_id=[1048])
    filename = tmp_path.joinpath("test.duckdb")
    request.values.to_target(f"duckdb:///{filename}?table=testdrive")
    # Second export with if_exists='fail' should raise an error
    with pytest.raises(KeyError) as exec_info:
        request.values.to_target(f"duckdb:///{filename}?table=testdrive", if_exists="fail")
    assert exec_info.match("Table 'testdrive' already exists in the database, aborting write due to if_exists='fail'.")


def test_export_duckdb_if_exists_replace(
    tmp_path: Path,
) -> None:
    """Test export of DataFrame to duckdb with if_exists='replace' parameter."""
    duckdb = pytest.importorskip("duckdb")

    filename = tmp_path.joinpath("test.duckdb")

    request = DwdObservationRequest(
        parameters=[("daily", "climate_summary")],
    ).filter_by_station_id(station_id=[1048])
    request.values.to_target(f"duckdb:///{filename}?table=testdrive")

    # Verify that the table exists and has station_id 1048
    conn = duckdb.connect(str(filename), read_only=False)
    assert conn.execute("SELECT DISTINCT station_id FROM testdrive").fetchall() == [("01048",)]

    request = DwdObservationRequest(
        parameters=[("daily", "climate_summary")],
    ).filter_by_station_id(station_id=[1050])
    request.to_target(f"duckdb:///{filename}?table=testdrive", if_exists="replace")
    # Verify that the table exists and has station_id 1050
    assert conn.execute("SELECT DISTINCT station_id FROM testdrive").fetchall() == [("01050",)]


def test_export_duckdb_if_exists_append(
    tmp_path: Path,
) -> None:
    """Test export of DataFrame to duckdb with if_exists='append' parameter."""
    duckdb = pytest.importorskip("duckdb")

    filename = tmp_path.joinpath("test.duckdb")

    request = DwdObservationRequest(
        parameters=[("daily", "climate_summary")],
    ).filter_by_station_id(station_id=[1048])
    request.values.to_target(f"duckdb:///{filename}?table=testdrive")

    # Verify that the table exists and has two entries for station_id 1048
    conn = duckdb.connect(str(filename), read_only=False)
    assert conn.execute("SELECT DISTINCT station_id FROM testdrive").fetchall()[0] == ("01048",)

    request = DwdObservationRequest(
        parameters=[("daily", "climate_summary")],
    ).filter_by_station_id(station_id=[1050])
    request.values.to_target(f"duckdb:///{filename}?table=testdrive", if_exists="append")
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

    request = DwdObservationRequest(
        parameters=[("daily", "climate_summary")],
    ).filter_by_station_id(station_id=[1048])
    request.values.to_target(f"duckdb:///{filename}?table=testdrive")

    # Verify that the table exists and has station_id 1048
    conn = duckdb.connect(str(filename), read_only=False)
    assert conn.execute("SELECT DISTINCT station_id FROM testdrive").fetchall() == [("01048",)]

    request = DwdObservationRequest(
        parameters=[("daily", "climate_summary")],
    ).filter_by_station_id(station_id=[1050])
    request.values.to_target(f"duckdb:///{filename}?table=testdrive", if_exists="skip")
    # Verify that the table still only has station_id 1048
    assert conn.execute("SELECT DISTINCT station_id FROM testdrive").fetchall() == [("01048",)]


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


def test_export_file_excel_if_exists_replace(tmp_path: Path) -> None:
    """Test export of DataFrame to Excel file with if_exists='replace' parameter."""
    pytest.importorskip("xlsxwriter")

    filename = tmp_path.joinpath("testfile.xlsx")

    request = DwdObservationRequest(
        parameters=[("daily", "climate_summary")],
    ).filter_by_station_id(station_id=[1048])

    values = request.values.all()
    values.to_target(f"file:///{filename}", if_exists="replace")
    assert filename.exists()


def test_export_file_append_exception() -> None:
    """Test export of DataFrame to file with if_exists='append' parameter."""
    request = DwdObservationRequest(
        parameters=[("daily", "climate_summary")],
    ).filter_by_station_id(station_id=[1048])

    values = request.values.all()
    with pytest.raises(NotImplementedError) as exec_info:
        values.to_target("file:///foo", if_exists="append")
    assert exec_info.match("Append mode is not supported for file exports.")


@pytest.mark.skipif(
    condition=IS_CI and IS_WINDOWS, reason="File existence check behaves differently on Windows CI environments."
)
def test_export_file_fail_exception(tmp_path: Path) -> None:
    """Test export of DataFrame to file with if_exists='fail' parameter."""
    filename = tmp_path.joinpath("testfile")
    filename.write_text("foo")

    request = DwdObservationRequest(
        parameters=[("daily", "climate_summary")],
    ).filter_by_station_id(station_id=[1048])

    values = request.values.all()
    with pytest.raises(FileExistsError) as exec_info:
        values.to_target(f"file:///{filename}", if_exists="fail")
    assert exec_info.match("File '.*testfile' already exists, aborting write due to if_exists='fail'.")
