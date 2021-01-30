# -*- coding: utf-8 -*-
# Copyright (c) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE.rst for more info.
import json

import dateutil.parser
import mock
import pandas as pd
import pytest
from surrogate import surrogate

from wetterdienst.dwd.observations import (
    DWDObservationData,
    DWDObservationParameterSet,
    DWDObservationPeriod,
    DWDObservationResolution,
)
from wetterdienst.metadata.resolution import Resolution

df_station = pd.DataFrame.from_dict(
    {
        "STATION_ID": ["19087"],
        "FROM_DATE": [dateutil.parser.isoparse("1957-05-01T00:00:00.000Z")],
        "TO_DATE": [dateutil.parser.isoparse("1995-11-30T00:00:00.000Z")],
        "HEIGHT": [645.0],
        "LATITUDE": [48.8049],
        "LONGITUDE": [13.5528],
        "STATION_NAME": ["Freyung vorm Wald"],
        "STATE": ["Bayern"],
        "HAS_FILE": [False],
    }
)

df_data = pd.DataFrame.from_dict(
    {
        "STATION_ID": ["01048"],
        "PARAMETER_SET": ["CLIMATE_SUMMARY"],
        "PARAMETER": ["TEMPERATURE_AIR_MAX_200"],
        "DATE": [dateutil.parser.isoparse("2019-12-28T00:00:00.000Z")],
        "VALUE": [1.3],
        "QUALITY": [None],
    }
)


def test_lowercase():

    df = df_data.dwd.lower()

    assert list(df.columns) == [
        "station_id",
        "parameter_set",
        "parameter",
        "date",
        "value",
        "quality",
    ]

    assert df.iloc[0]["parameter_set"] == "climate_summary"
    assert df.iloc[0]["parameter"] == "temperature_air_max_200"


def test_filter_by_date():

    df = df_data.dwd.filter_by_date("2019-12-28", Resolution.HOURLY)
    assert not df.empty

    df = df_data.dwd.filter_by_date("2019-12-27", Resolution.HOURLY)
    assert df.empty


def test_filter_by_date_interval():

    df = df_data.dwd.filter_by_date("2019-12-27/2019-12-29", Resolution.HOURLY)
    assert not df.empty

    df = df_data.dwd.filter_by_date("2020/2022", Resolution.HOURLY)
    assert df.empty


def test_filter_by_date_monthly():

    result = pd.DataFrame.from_dict(
        {
            "STATION_ID": ["01048"],
            "PARAMETER": ["climate_summary"],
            "ELEMENT": ["temperature_air_max_200"],
            "FROM_DATE": [dateutil.parser.isoparse("2019-12-28T00:00:00.000Z")],
            "TO_DATE": [dateutil.parser.isoparse("2020-01-28T00:00:00.000Z")],
            "VALUE": [1.3],
            "QUALITY": [None],
        }
    )

    df = result.dwd.filter_by_date("2019-12/2020-01", Resolution.MONTHLY)
    assert not df.empty

    df = result.dwd.filter_by_date("2020/2022", Resolution.MONTHLY)
    assert df.empty

    df = result.dwd.filter_by_date("2020", Resolution.MONTHLY)
    assert df.empty


def test_filter_by_date_annual():

    result = pd.DataFrame.from_dict(
        {
            "STATION_ID": ["01048"],
            "PARAMETER_SET": ["climate_summary"],
            "PARAMETER": ["temperature_air_max_200"],
            "FROM_DATE": [dateutil.parser.isoparse("2019-01-01T00:00:00.000Z")],
            "TO_DATE": [dateutil.parser.isoparse("2019-12-31T00:00:00.000Z")],
            "VALUE": [1.3],
            "QUALITY": [None],
        }
    )

    df = result.dwd.filter_by_date("2019-05/2019-09", Resolution.ANNUAL)
    assert not df.empty

    df = result.dwd.filter_by_date("2020/2022", Resolution.ANNUAL)
    assert df.empty

    df = result.dwd.filter_by_date("2020", Resolution.ANNUAL)
    assert df.empty


@pytest.mark.sql
def test_filter_by_sql():
    # TODO: change this to a test of historical data
    df = df_data.dwd.lower().io.sql(
        "SELECT * FROM data WHERE parameter='temperature_air_max_200' AND value < 1.5"
    )
    assert not df.empty

    df = df_data.dwd.lower().io.sql(
        "SELECT * FROM data WHERE parameter='temperature_air_max_200' AND value > 1.5"
    )
    assert df.empty


def test_format_json():

    output = df_data.dwd.lower().io.format("json")

    response = json.loads(output)
    station_ids = list(set([reading["station_id"] for reading in response]))

    assert "01048" in station_ids


def test_format_geojson():

    output = df_station.dwd.format("geojson")

    response = json.loads(output)

    station_names = [station["properties"]["name"] for station in response["features"]]

    assert "Freyung vorm Wald" in station_names


def test_format_csv():

    output = df_data.dwd.lower().io.format("csv").strip()

    assert "station_id,parameter_set,parameter,date,value,quality" in output
    assert (
        "01048,climate_summary,temperature_air_max_200,2019-12-28T00-00-00,1.3,"
        in output
    )


def test_format_unknown():

    with pytest.raises(KeyError):
        df_data.dwd.format("foobar")


def test_request():

    observations = DWDObservationData(
        station_ids=[1048],
        parameters=DWDObservationParameterSet.CLIMATE_SUMMARY,
        resolution=DWDObservationResolution.DAILY,
        periods=DWDObservationPeriod.RECENT,
    )

    df = observations.all()
    assert not df.empty


def test_export_sqlite():

    observations = DWDObservationData(
        station_ids=[1048],
        parameters=DWDObservationParameterSet.CLIMATE_SUMMARY,
        resolution=DWDObservationResolution.DAILY,
        periods=DWDObservationPeriod.RECENT,
    )

    with mock.patch(
        "pandas.DataFrame.to_sql",
    ) as mock_to_sql:

        df = observations.all()
        df.io.export("sqlite:///test.sqlite?table=testdrive")

        mock_to_sql.assert_called_once_with(
            name="testdrive",
            con="sqlite:///test.sqlite?table=testdrive",
            if_exists="replace",
            index=False,
            method="multi",
            chunksize=5000,
        )


def test_export_crate():

    observations = DWDObservationData(
        station_ids=[1048],
        parameters=DWDObservationParameterSet.CLIMATE_SUMMARY,
        resolution=DWDObservationResolution.DAILY,
        periods=DWDObservationPeriod.RECENT,
    )

    with mock.patch(
        "pandas.DataFrame.to_sql",
    ) as mock_to_sql:

        df = observations.all()
        df.io.export("crate://localhost/?database=test&table=testdrive")

        mock_to_sql.assert_called_once_with(
            name="testdrive",
            con="crate://localhost/?database=test&table=testdrive",
            if_exists="replace",
            index=False,
            method="multi",
            chunksize=5000,
        )


@surrogate("duckdb.connect")
def test_export_duckdb():

    observations = DWDObservationData(
        station_ids=[1048],
        parameters=DWDObservationParameterSet.CLIMATE_SUMMARY,
        resolution=DWDObservationResolution.DAILY,
        periods=DWDObservationPeriod.RECENT,
    )

    mock_connection = mock.MagicMock()
    with mock.patch(
        "duckdb.connect", side_effect=[mock_connection], create=True
    ) as mock_connect:

        df = observations.all()
        df.io.export("duckdb:///test.duckdb?table=testdrive")

        mock_connect.assert_called_once_with(database="test.duckdb", read_only=False)
        mock_connection.register.assert_called_once()
        mock_connection.execute.assert_called()
        mock_connection.table.assert_called_once_with("testdrive")
        # a.table.to_df.assert_called()
        mock_connection.close.assert_called_once()


@surrogate("influxdb.dataframe_client.DataFrameClient")
def test_export_influxdb_tabular():

    observations = DWDObservationData(
        station_ids=[1048],
        parameters=DWDObservationParameterSet.CLIMATE_SUMMARY,
        resolution=DWDObservationResolution.DAILY,
        periods=DWDObservationPeriod.RECENT,
        tidy_data=False,
    )

    mock_client = mock.MagicMock()
    with mock.patch(
        "influxdb.dataframe_client.DataFrameClient",
        side_effect=[mock_client],
        create=True,
    ) as mock_connect:

        df = observations.all()
        df.dwd.lower().io.export("influxdb://localhost/?database=dwd&table=weather")

        mock_connect.assert_called_once_with(database="dwd")
        mock_client.create_database.assert_called_once_with("dwd")
        mock_client.write_points.assert_called_once()

        mock_client.write_points.assert_called_with(
            dataframe=mock.ANY,
            measurement="weather",
            tag_columns=["station_id", "quality"],
            batch_size=50000,
        )


@surrogate("influxdb.dataframe_client.DataFrameClient")
def test_export_influxdb_tidy():

    observations = DWDObservationData(
        station_ids=[1048],
        parameters=DWDObservationParameterSet.CLIMATE_SUMMARY,
        resolution=DWDObservationResolution.DAILY,
        periods=DWDObservationPeriod.RECENT,
        tidy_data=True,
    )

    mock_client = mock.MagicMock()
    with mock.patch(
        "influxdb.dataframe_client.DataFrameClient",
        side_effect=[mock_client],
        create=True,
    ) as mock_connect:

        df = observations.all()
        df.dwd.lower().io.export("influxdb://localhost/?database=dwd&table=weather")

        mock_connect.assert_called_once_with(database="dwd")
        mock_client.create_database.assert_called_once_with("dwd")
        mock_client.write_points.assert_called_once()

        mock_client.write_points.assert_called_with(
            dataframe=mock.ANY,
            measurement="weather",
            tag_columns=["station_id", "quality", "parameter_set", "parameter"],
            batch_size=50000,
        )
