# -*- coding: utf-8 -*-
# Copyright (c) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
import datetime
import json
import os
import shutil

import dateutil.parser
import mock
import pandas as pd
import pytest
from surrogate import surrogate

from tests import mac_arm64_unsupported
from wetterdienst.core.process import filter_by_date_and_resolution
from wetterdienst.core.scalar.export import ExportMixin
from wetterdienst.core.scalar.result import StationsResult
from wetterdienst.metadata.resolution import Resolution
from wetterdienst.provider.dwd.observation import (
    DwdObservationDataset,
    DwdObservationPeriod,
    DwdObservationRequest,
    DwdObservationResolution,
)

df_station = pd.DataFrame.from_dict(
    {
        "station_id": ["19087"],
        "from_date": [dateutil.parser.isoparse("1957-05-01T00:00:00.000Z")],
        "to_date": [dateutil.parser.isoparse("1995-11-30T00:00:00.000Z")],
        "height": [645.0],
        "latitude": [48.8049],
        "longitude": [13.5528],
        "name": ["Freyung vorm Wald"],
        "state": ["Bayern"],
        "has_file": [False],
    }
)

df_data = pd.DataFrame.from_dict(
    {
        "station_id": ["01048"],
        "dataset": ["climate_summary"],
        "parameter": ["temperature_air_max_200"],
        "date": [dateutil.parser.isoparse("2019-12-28T00:00:00.000Z")],
        "value": [1.3],
        "quality": [None],
    }
)


def test_to_dict():

    data = ExportMixin(df=df_data).to_dict()

    assert data == [
        {
            "dataset": "climate_summary",
            "date": "2019-12-28T00:00:00+00:00",
            "parameter": "temperature_air_max_200",
            "quality": None,
            "station_id": "01048",
            "value": 1.3,
        },
    ]


def test_filter_by_date():

    df = filter_by_date_and_resolution(df_data, "2019-12-28", Resolution.HOURLY)
    assert not df.empty

    df = filter_by_date_and_resolution(df_data, "2019-12-27", Resolution.HOURLY)
    assert df.empty


def test_filter_by_date_interval():

    df = filter_by_date_and_resolution(
        df_data, "2019-12-27/2019-12-29", Resolution.HOURLY
    )
    assert not df.empty

    df = filter_by_date_and_resolution(df_data, "2020/2022", Resolution.HOURLY)
    assert df.empty


def test_filter_by_date_monthly():

    result = pd.DataFrame.from_dict(
        {
            "station_id": ["01048"],
            "dataset": ["climate_summary"],
            "parameter": ["temperature_air_max_200"],
            "from_date": [dateutil.parser.isoparse("2019-12-28T00:00:00.000Z")],
            "to_date": [dateutil.parser.isoparse("2020-01-28T00:00:00.000Z")],
            "value": [1.3],
            "quality": [None],
        }
    )

    df = filter_by_date_and_resolution(result, "2019-12/2020-01", Resolution.MONTHLY)
    assert not df.empty

    df = filter_by_date_and_resolution(result, "2020/2022", Resolution.MONTHLY)
    assert df.empty

    df = filter_by_date_and_resolution(result, "2020", Resolution.MONTHLY)
    assert df.empty


def test_filter_by_date_annual():

    df = pd.DataFrame.from_dict(
        {
            "station_id": ["01048"],
            "dataset": ["climate_summary"],
            "parameter": ["temperature_air_max_200"],
            "from_date": [dateutil.parser.isoparse("2019-01-01T00:00:00.000Z")],
            "to_date": [dateutil.parser.isoparse("2019-12-31T00:00:00.000Z")],
            "value": [1.3],
            "quality": [None],
        }
    )

    df = filter_by_date_and_resolution(
        df, date="2019-05/2019-09", resolution=Resolution.ANNUAL
    )
    assert not df.empty

    df = filter_by_date_and_resolution(
        df, date="2020/2022", resolution=Resolution.ANNUAL
    )
    assert df.empty

    df = filter_by_date_and_resolution(df, date="2020", resolution=Resolution.ANNUAL)
    assert df.empty


@pytest.mark.sql
def test_filter_by_sql():
    # TODO: change this to a test of historical data
    df = ExportMixin(df=df_data).filter_by_sql(
        "SELECT * FROM data WHERE parameter='temperature_air_max_200' AND value < 1.5"
    )
    assert not df.empty

    df = ExportMixin(df=df_data).filter_by_sql(
        "SELECT * FROM data WHERE parameter='temperature_air_max_200' AND value > 1.5"
    )
    assert df.empty


def test_format_json():

    output = ExportMixin(df=df_data).to_json()

    response = json.loads(output)
    station_ids = list(set([reading["station_id"] for reading in response]))

    assert "01048" in station_ids


def test_format_geojson():

    output = StationsResult(df=df_station, stations=None).to_geojson()

    response = json.loads(output)

    station_names = [station["properties"]["name"] for station in response["features"]]

    assert "Freyung vorm Wald" in station_names


def test_format_csv():

    output = ExportMixin(df=df_data).to_csv().strip()

    assert "station_id,dataset,parameter,date,value,quality" in output
    assert (
        "01048,climate_summary,temperature_air_max_200,2019-12-28T00-00-00,1.3,"
        in output
    )


def test_request():

    request = DwdObservationRequest(
        parameter=DwdObservationDataset.CLIMATE_SUMMARY,
        resolution=DwdObservationResolution.DAILY,
        period=DwdObservationPeriod.RECENT,
    ).filter_by_station_id(station_id=[1048])

    df = request.values.all().df

    assert not df.empty


def test_export_unknown():

    request = DwdObservationRequest(
        parameter=DwdObservationDataset.CLIMATE_SUMMARY,
        resolution=DwdObservationResolution.DAILY,
        period=DwdObservationPeriod.RECENT,
    ).filter_by_station_id(
        station_id=[1048],
    )

    df = request.values.all().df

    with pytest.raises(KeyError) as ex:
        ExportMixin(df=df).to_target("file:///test.foobar")

    ex.match("Unknown export file type")


def test_export_spreadsheet(tmpdir_factory):

    import openpyxl

    # 1. Request data and save to .xlsx file.
    request = DwdObservationRequest(
        parameter=DwdObservationDataset.CLIMATE_SUMMARY,
        resolution=DwdObservationResolution.DAILY,
        start_date="2019",
        end_date="2020",
        tidy=False,
        si_units=False,
    ).filter_by_station_id(
        station_id=[1048],
    )

    df = request.values.all().df

    filename = tmpdir_factory.mktemp("data").join("observations.xlsx")
    ExportMixin(df=df).to_target(f"file://{filename}")

    workbook = openpyxl.load_workbook(filename=filename)
    worksheet = workbook.active

    # 2. Validate some details of .xlsx file.

    # Validate header row.
    header = list(worksheet.iter_cols(min_row=1, max_row=1, values_only=True))
    assert header == [
        ("station_id",),
        ("date",),
        ("qn_3",),
        ("wind_gust_max",),
        ("wind_speed",),
        ("qn_4",),
        ("precipitation_height",),
        ("precipitation_form",),
        ("sunshine_duration",),
        ("snow_depth",),
        ("cloud_cover_total",),
        ("pressure_vapor",),
        ("pressure_air",),
        ("temperature_air_200",),
        ("humidity",),
        ("temperature_air_max_200",),
        ("temperature_air_min_200",),
        ("temperature_air_min_005",),
    ]

    # Validate number of records.
    assert worksheet.max_row == 367

    first_record = list(worksheet.iter_cols(min_row=2, max_row=2, values_only=True))
    assert first_record == [
        ("01048",),
        ("2019-01-01T00:00:00+00:00",),
        (10,),
        (19.9,),
        (8.5,),
        (3,),
        (0.9,),
        (8,),
        (0,),
        (0,),
        (7.4,),
        (7.9,),
        (991.87,),
        (5.9,),
        (84.21,),
        (7.5,),
        (2,),
        (1.5,),
    ]

    last_record = list(
        worksheet.iter_cols(
            min_row=worksheet.max_row, max_row=worksheet.max_row, values_only=True
        )
    )
    assert last_record == [
        ("01048",),
        ("2020-01-01T00:00:00+00:00",),
        (10,),
        (6.9,),
        (3.2,),
        (3,),
        (0,),
        (0,),
        (3.933,),
        (0,),
        (4.2,),
        (5.7,),
        (1005.11,),
        (2.4,),
        (79,),
        (5.6,),
        (-2.8,),
        (-4.6,),
    ]

    os.unlink(filename)


@mac_arm64_unsupported
def test_export_parquet(tmpdir_factory):

    import pyarrow.parquet as pq

    # Request data.
    request = DwdObservationRequest(
        parameter=DwdObservationDataset.CLIMATE_SUMMARY,
        resolution=DwdObservationResolution.DAILY,
        start_date="2019",
        end_date="2020",
        tidy=False,
        si_units=False,
    ).filter_by_station_id(
        station_id=[1048],
    )

    df = request.values.all().df

    # Save to Parquet file.
    filename = tmpdir_factory.mktemp("data").join("observations.parquet")
    ExportMixin(df=df).to_target(f"file://{filename}")

    # Read back Parquet file.
    table = pq.read_table(filename)

    # Validate dimensions.
    assert table.num_columns == 18
    assert table.num_rows == 366

    # Validate column names.
    assert table.column_names == [
        "station_id",
        "date",
        "qn_3",
        "wind_gust_max",
        "wind_speed",
        "qn_4",
        "precipitation_height",
        "precipitation_form",
        "sunshine_duration",
        "snow_depth",
        "cloud_cover_total",
        "pressure_vapor",
        "pressure_air",
        "temperature_air_200",
        "humidity",
        "temperature_air_max_200",
        "temperature_air_min_200",
        "temperature_air_min_005",
    ]

    # Validate content.
    data = table.to_pydict()

    assert data["date"][0] == datetime.datetime(
        2019, 1, 1, 0, 0, tzinfo=datetime.timezone.utc
    )
    assert data["temperature_air_min_005"][0] == 1.5
    assert data["date"][-1] == datetime.datetime(
        2020, 1, 1, 0, 0, tzinfo=datetime.timezone.utc
    )
    assert data["temperature_air_min_005"][-1] == -4.6

    os.unlink(filename)


@mac_arm64_unsupported
def test_export_zarr(tmpdir_factory):

    import numpy as np
    import zarr

    # Request data.
    request = DwdObservationRequest(
        parameter=DwdObservationDataset.CLIMATE_SUMMARY,
        resolution=DwdObservationResolution.DAILY,
        start_date="2019",
        end_date="2020",
        tidy=False,
        si_units=False,
    ).filter_by_station_id(
        station_id=[1048],
    )

    df = request.values.all().df

    # Save to Zarr group.
    filename = tmpdir_factory.mktemp("data").join("observations.zarr")
    ExportMixin(df=df).to_target(f"file://{filename}")

    # Read back Zarr group.
    group = zarr.open(str(filename), mode="r")

    # Validate dimensions.
    assert len(group) == 19
    assert len(group.index) == 366

    # Validate column names.
    assert set(group.keys()) == {
        "index",
        "station_id",
        "date",
        "qn_3",
        "wind_gust_max",
        "wind_speed",
        "qn_4",
        "precipitation_height",
        "precipitation_form",
        "sunshine_duration",
        "snow_depth",
        "cloud_cover_total",
        "pressure_vapor",
        "pressure_air",
        "temperature_air_200",
        "humidity",
        "temperature_air_max_200",
        "temperature_air_min_200",
        "temperature_air_min_005",
    }

    # Validate content.
    data = group

    assert data["date"][0] == np.datetime64(
        datetime.datetime(2019, 1, 1, 0, 0, tzinfo=datetime.timezone.utc)
    )
    assert data["temperature_air_min_005"][0] == 1.5
    assert data["date"][-1] == np.datetime64(
        datetime.datetime(2020, 1, 1, 0, 0, tzinfo=datetime.timezone.utc)
    )
    assert data["temperature_air_min_005"][-1] == -4.6

    shutil.rmtree(filename)


@mac_arm64_unsupported
def test_export_feather(tmpdir_factory):

    import pyarrow.feather as feather

    # Request data
    request = DwdObservationRequest(
        parameter=DwdObservationDataset.CLIMATE_SUMMARY,
        resolution=DwdObservationResolution.DAILY,
        start_date="2019",
        end_date="2020",
        tidy=False,
        si_units=False,
    ).filter_by_station_id(
        station_id=[1048],
    )

    df = request.values.all().df

    # Save to Feather file.
    filename = tmpdir_factory.mktemp("data").join("observations.feather")
    ExportMixin(df=df).to_target(f"file://{filename}")

    # Read back Feather file.
    table = feather.read_table(filename)

    # Validate dimensions.
    assert table.num_columns == 18
    assert table.num_rows == 366

    # Validate column names.
    assert table.column_names == [
        "station_id",
        "date",
        "qn_3",
        "wind_gust_max",
        "wind_speed",
        "qn_4",
        "precipitation_height",
        "precipitation_form",
        "sunshine_duration",
        "snow_depth",
        "cloud_cover_total",
        "pressure_vapor",
        "pressure_air",
        "temperature_air_200",
        "humidity",
        "temperature_air_max_200",
        "temperature_air_min_200",
        "temperature_air_min_005",
    ]

    # Validate content.
    data = table.to_pydict()

    assert data["date"][0] == datetime.datetime(
        2019, 1, 1, 0, 0, tzinfo=datetime.timezone.utc
    )
    assert data["temperature_air_min_005"][0] == 1.5
    assert data["date"][-1] == datetime.datetime(
        2020, 1, 1, 0, 0, tzinfo=datetime.timezone.utc
    )
    assert data["temperature_air_min_005"][-1] == -4.6

    os.unlink(filename)


def test_export_sqlite(tmpdir_factory):

    import sqlite3

    request = DwdObservationRequest(
        parameter=DwdObservationDataset.CLIMATE_SUMMARY,
        resolution=DwdObservationResolution.DAILY,
        start_date="2019",
        end_date="2020",
        tidy=False,
        si_units=False,
    ).filter_by_station_id(
        station_id=[1048],
    )

    filename = tmpdir_factory.mktemp("data").join("observations.sqlite")

    df = request.values.all().df
    ExportMixin(df=df).to_target(f"sqlite:///{filename}?table=testdrive")

    connection = sqlite3.connect(filename)
    cursor = connection.cursor()
    cursor.execute("SELECT * FROM testdrive")
    results = cursor.fetchall()
    cursor.close()
    connection.close()

    assert results[0] == (
        "01048",
        "2019-01-01 00:00:00.000000",
        10,
        19.9,
        8.5,
        3,
        0.9,
        8,
        0.0,
        0,
        7.4,
        7.9,
        991.87,
        5.9,
        84.21,
        7.5,
        2.0,
        1.5,
    )

    assert results[-1] == (
        "01048",
        "2020-01-01 00:00:00.000000",
        10,
        6.9,
        3.2,
        3,
        0.0,
        0,
        3.933,
        0,
        4.2,
        5.7,
        1005.11,
        2.4,
        79.0,
        5.6,
        -2.8,
        -4.6,
    )


def test_export_cratedb():

    request = DwdObservationRequest(
        parameter=DwdObservationDataset.CLIMATE_SUMMARY,
        resolution=DwdObservationResolution.DAILY,
        period=DwdObservationPeriod.RECENT,
        si_units=False,
    ).filter_by_station_id(
        station_id=[1048],
    )

    with mock.patch(
        "pandas.DataFrame.to_sql",
    ) as mock_to_sql:

        df = request.values.all().df
        ExportMixin(df=df).to_target("crate://localhost/?database=test&table=testdrive")

        mock_to_sql.assert_called_once_with(
            name="testdrive",
            con="crate://localhost",
            schema="test",
            if_exists="replace",
            index=False,
            # method="multi",
            chunksize=5000,
        )


@surrogate("duckdb.connect")
def test_export_duckdb():

    request = DwdObservationRequest(
        parameter=DwdObservationDataset.CLIMATE_SUMMARY,
        resolution=DwdObservationResolution.DAILY,
        period=DwdObservationPeriod.RECENT,
        si_units=False,
    ).filter_by_station_id(station_id=[1048])

    mock_connection = mock.MagicMock()
    with mock.patch(
        "duckdb.connect", side_effect=[mock_connection], create=True
    ) as mock_connect:

        df = request.values.all().df
        ExportMixin(df=df).to_target("duckdb:///test.duckdb?table=testdrive")

        mock_connect.assert_called_once_with(database="test.duckdb", read_only=False)
        mock_connection.register.assert_called_once()
        mock_connection.execute.assert_called()
        mock_connection.table.assert_called_once_with("testdrive")
        # a.table.to_df.assert_called()
        mock_connection.close.assert_called_once()


@surrogate("influxdb.dataframe_client.DataFrameClient")
def test_export_influxdb_tabular():

    request = DwdObservationRequest(
        parameter=DwdObservationDataset.CLIMATE_SUMMARY,
        resolution=DwdObservationResolution.DAILY,
        period=DwdObservationPeriod.RECENT,
        tidy=False,
        si_units=False,
    ).filter_by_station_id(station_id=[1048])

    mock_client = mock.MagicMock()
    with mock.patch(
        "influxdb.dataframe_client.DataFrameClient",
        side_effect=[mock_client],
        create=True,
    ) as mock_connect:

        df = request.values.all().df
        ExportMixin(df=df).to_target("influxdb://localhost/?database=dwd&table=weather")

        mock_connect.assert_called_once_with(database="dwd")
        mock_client.create_database.assert_called_once_with("dwd")
        mock_client.write_points.assert_called_once()

        mock_client.write_points.assert_called_with(
            dataframe=mock.ANY,
            measurement="weather",
            tag_columns=["station_id", "qn_3", "qn_4"],
            batch_size=50000,
        )


@surrogate("influxdb.dataframe_client.DataFrameClient")
def test_export_influxdb_tidy():

    request = DwdObservationRequest(
        parameter=DwdObservationDataset.CLIMATE_SUMMARY,
        resolution=DwdObservationResolution.DAILY,
        period=DwdObservationPeriod.RECENT,
        tidy=True,
        si_units=False,
    ).filter_by_station_id(station_id=[1048])

    mock_client = mock.MagicMock()
    with mock.patch(
        "influxdb.dataframe_client.DataFrameClient",
        side_effect=[mock_client],
        create=True,
    ) as mock_connect:

        df = request.values.all().df
        ExportMixin(df=df).to_target("influxdb://localhost/?database=dwd&table=weather")

        mock_connect.assert_called_once_with(database="dwd")
        mock_client.create_database.assert_called_once_with("dwd")
        mock_client.write_points.assert_called_once()

        mock_client.write_points.assert_called_with(
            dataframe=mock.ANY,
            measurement="weather",
            tag_columns=["station_id", "quality", "dataset", "parameter"],
            batch_size=50000,
        )
