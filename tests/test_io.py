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
            "start_date": "1957-05-01T00:00:00+00:00",
            "end_date": "1995-11-30T00:00:00+00:00",
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
            "start_date": "1957-05-01T00:00:00+00:00",
            "end_date": "1995-11-30T00:00:00+00:00",
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
        lines[1] == "daily,climate_summary,01048,1957-05-01T00:00:00+00:00,1995-11-30T00:00:00+00:00,"
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
            "date": "2019-01-01T00:00:00+00:00",
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
            "start_date": "1957-05-01T00:00:00+00:00",
            "end_date": "1995-11-30T00:00:00+00:00",
        },
        "type": "Feature",
        "values": [
            {
                "resolution": "daily",
                "dataset": "climate_summary",
                "parameter": "temperature_air_max_2m",
                "date": "2019-01-01T00:00:00+00:00",
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
        "date": "2019-01-01T00:00:00+00:00",
        "value": 1.3,
        "quality": None,
    }


def test_values_format_csv(df_values: pl.DataFrame) -> None:
    """Test export of DataFrame to csv."""
    output = ValuesResult(stations=None, values=None, df=df_values).to_csv().strip()
    lines = output.split("\n")
    assert lines[0] == "station_id,resolution,dataset,parameter,date,value,quality"
    assert lines[-1] == "01048,daily,climate_summary,temperature_air_max_2m,2022-01-01T00:00:00+00:00,4.0,"


def test_values_format_csv_kwargs(df_values: pl.DataFrame) -> None:
    """Test export of DataFrame to csv."""
    output = ValuesResult(stations=None, values=None, df=df_values).to_csv(include_header=False).strip()
    lines = output.split("\n")
    assert lines[0] == "01048,daily,climate_summary,temperature_air_max_2m,2019-01-01T00:00:00+00:00,1.3,"


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
            "date": "2019-01-01T00:00:00+00:00",
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
    assert lines[0] == 'abc,daily,climate_summary,temperature_air_max_2m,2019-01-01T00:00:00+00:00,1.3,5.3,"01048,1050"'


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
        "properties": {"id": "abc", "name": "interpolation(1.2345,2.3456)"},
        "stations": [
            {
                "resolution": "daily",
                "dataset": "climate_summary",
                "station_id": "01048",
                "start_date": "1957-05-01T00:00:00+00:00",
                "end_date": "1995-11-30T00:00:00+00:00",
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
                "date": "2019-01-01T00:00:00+00:00",
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
            "date": "2019-01-01T00:00:00+00:00",
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
    assert lines[0] == "abc,daily,climate_summary,temperature_air_max_2m,2019-01-01T00:00:00+00:00,1.3,0.0,01048"


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
        "properties": {"id": "abc", "name": "summary(1.2345,2.3456)"},
        "stations": [
            {
                "resolution": "daily",
                "dataset": "climate_summary",
                "station_id": "01048",
                "start_date": "1957-05-01T00:00:00+00:00",
                "end_date": "1995-11-30T00:00:00+00:00",
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
                "date": "2019-01-01T00:00:00+00:00",
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
        "date": "2019-01-01T00:00:00+00:00",
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
        "date": "2020-01-01T00:00:00+00:00",
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
    assert len(group.index) == 366
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
def test_export_feather(
    settings_convert_units_false_wide_shape: Settings,
    dwd_climate_summary_tabular_columns: list[str],
    tmp_path: Path,
) -> None:
    """Test export of DataFrame to feather."""
    feather = pytest.importorskip("pyarrow.feather")
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
    table = feather.read_table(filename)
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
        assert first_point["time"] == "2019-01-01T00:00:00+00:00"
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
