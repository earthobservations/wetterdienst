""" Tests for data_collection """
import pytest
from pathlib import Path
from io import StringIO, BytesIO

import pandas as pd
from pandas._testing import assert_frame_equal
from mock import MagicMock, patch

from wetterdienst.dwd.observations.access import (
    collect_climate_observations_data,
    _tidy_up_data,
)
from wetterdienst.dwd.metadata.parameter import Parameter
from wetterdienst import TimeResolution
from wetterdienst.dwd.metadata.period_type import PeriodType
from wetterdienst.dwd.util import coerce_field_types

HERE = Path(__file__).parent

# Set filename for mock
filename = "tageswerte_KL_00001_19370101_19860630_hist.zip"

# Loading test data
TEST_FILE = pd.read_json(HERE / "FIXED_STATIONDATA.JSON")

# Prepare csv for regular "downloading" test
CSV_FILE = StringIO()
TEST_FILE.to_csv(CSV_FILE, sep=";", index=False)
CSV_FILE.seek(0)


@patch(
    "wetterdienst.dwd.observations.access.create_file_list_for_climate_observations",
    MagicMock(return_value=[filename]),
)
@patch(
    "wetterdienst.dwd.observations.access.download_climate_observations_data_parallel",
    MagicMock(return_value=[(filename, BytesIO(CSV_FILE.read().encode()))]),
)
def test_collect_dwd_data_success():
    """ Test for data collection """
    """
    1. Scenario
    This scenario makes sure we take fresh data and write it to the given folder, thus
    we can run just another test afterwards as no old data is used
    """
    df = collect_climate_observations_data(
        station_ids=[1],
        parameter=Parameter.CLIMATE_SUMMARY,
        time_resolution=TimeResolution.DAILY,
        period_type=PeriodType.HISTORICAL,
        prefer_local=False,
        write_file=True,
        tidy_data=False,
    )

    assert_frame_equal(
        df, coerce_field_types(TEST_FILE, TimeResolution.DAILY), check_column_type=False
    )

    """
    2. Scenario
    This scenario tries to get the data from the given folder. This data was placed by
    the first test and is now restored
    """
    df = collect_climate_observations_data(
        station_ids=[1],
        parameter=Parameter.CLIMATE_SUMMARY,
        time_resolution=TimeResolution.DAILY,
        period_type=PeriodType.HISTORICAL,
        prefer_local=True,
        write_file=True,
        tidy_data=False,
    )

    assert_frame_equal(
        df, coerce_field_types(TEST_FILE, TimeResolution.DAILY), check_column_type=False
    )


@patch(
    "wetterdienst.dwd.observations.access.restore_climate_observations",
    MagicMock(return_value=pd.DataFrame()),
)
@patch(
    "wetterdienst.dwd.observations.access.create_file_list_for_climate_observations",
    MagicMock(return_value=[]),
)
def test_collect_dwd_data_empty():
    """ Test for data collection with no available data """
    # mocked_restore_climate_observations.return_value.data = pd.DataFrame()
    # mocked_create_file_list_for_climate_observations.return_value = []
    """
    1. Scenario
    Test for request where no data is available
    """
    # create_file_index_for_climate_observations.invalidate()

    assert collect_climate_observations_data(
        station_ids=[1048],
        parameter=Parameter.CLIMATE_SUMMARY,
        time_resolution=TimeResolution.DAILY,
        period_type=PeriodType.RECENT,
        prefer_local=True,
        write_file=False,
        tidy_data=False,
    ).empty


@pytest.mark.remote
def test_collect_daily_vanilla():
    """ Test for data collection with real data """

    data = collect_climate_observations_data(
        station_ids=[1048],
        parameter=Parameter.CLIMATE_SUMMARY,
        time_resolution=TimeResolution.DAILY,
        period_type=PeriodType.RECENT,
        tidy_data=False,
    )

    assert list(data.columns.values) == [
        "STATION_ID",
        "DATE",
        "QN_3",
        "FX",
        "FM",
        "QN_4",
        "RSK",
        "RSKF",
        "SDK",
        "SHK_TAG",
        "NM",
        "VPM",
        "PM",
        "TMK",
        "UPM",
        "TXK",
        "TNK",
        "TGK",
    ]


@pytest.mark.remote
def test_collect_hourly_vanilla():
    """ Test for data collection with real data """

    data = collect_climate_observations_data(
        station_ids=[1048],
        parameter=Parameter.TEMPERATURE_AIR,
        time_resolution=TimeResolution.HOURLY,
        period_type=PeriodType.RECENT,
        tidy_data=False,
    )

    assert list(data.columns.values) == [
        "STATION_ID",
        "DATE",
        "QN_9",
        "TT_TU",
        "RF_TU",
    ]


def test_tidy_up_data():
    """ Test for function to tidy data"""
    df = pd.DataFrame(
        {
            "STATION_ID": [1048],
            "DATE": [pd.Timestamp("2019-01-23 00:00:00")],
            "QN_3": [10],
            "FX": [11.8],
            "FM": [5.8],
            "QN_4": [3],
            "RSK": [0.0],
            "RSKF": [0.0],
            "SDK": [7.1],
            "SHK_TAG": [0.0],
            "NM": [2.3],
            "VPM": [3.2],
            "PM": [975.4],
            "TMK": [-5.5],
            "UPM": [79.17],
            "TXK": [-1.7],
            "TNK": [-7.9],
            "TGK": [-11.4],
        }
    )

    df_tidy = pd.DataFrame(
        {
            "STATION_ID": [1048] * 14,
            "PARAMETER": ["CLIMATE_SUMMARY"] * 14,
            "ELEMENT": [
                "FX",
                "FM",
                "RSK",
                "RSKF",
                "SDK",
                "SHK_TAG",
                "NM",
                "VPM",
                "PM",
                "TMK",
                "UPM",
                "TXK",
                "TNK",
                "TGK",
            ],
            "DATE": [pd.Timestamp("2019-01-23 00:00:00")] * 14,
            "VALUE": [
                11.8,
                5.8,
                0.0,
                0.0,
                7.1,
                0.0,
                2.3,
                3.2,
                975.4,
                -5.5,
                79.17,
                -1.7,
                -7.9,
                -11.4,
            ],
            "QUALITY": [10, 10, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3],
        }
    )

    assert _tidy_up_data(df, Parameter.CLIMATE_SUMMARY).equals(df_tidy)
