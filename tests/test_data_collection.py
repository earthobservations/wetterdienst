""" Tests for data_collection """
import mock
import pytest
from mock import patch
from pathlib import Path
import pandas as pd
from io import StringIO, BytesIO
from shutil import rmtree

from wetterdienst.enumerations.column_names_enumeration import DWDMetaColumns
from wetterdienst.enumerations.parameter_enumeration import Parameter
from wetterdienst.enumerations.time_resolution_enumeration import TimeResolution
from wetterdienst.enumerations.period_type_enumeration import PeriodType
from wetterdienst.data_collection import collect_dwd_data, _tidy_up_data

# Create folder for storage test
test_folder = Path(Path(__file__).parent.absolute() / "dwd_data")
test_folder.mkdir(parents=True, exist_ok=True)

fixtures_dir = Path(__file__, "../").resolve().absolute() / "fixtures"

# Set filename for mock
filename = "tageswerte_KL_00001_19370101_19860630_hist.zip"

# Loading test data
file = pd.read_json(fixtures_dir / "FIXED_STATIONDATA.JSON")

# Prepare csv for regular "downloading" test
csv_file = StringIO()
file.to_csv(csv_file, sep=";")
csv_file.seek(0)


@patch(
    "wetterdienst.data_collection.create_file_list_for_dwd_server",
    mock.MagicMock(
        return_value=pd.DataFrame({DWDMetaColumns.FILENAME.value: [filename]})
    ),
)
@patch(
    "wetterdienst.data_collection.download_dwd_data_parallel",
    mock.MagicMock(return_value=[(filename, BytesIO(csv_file.read().encode()))]),
)
def test_collect_dwd_data():
    """ Test for data collection """
    """
    1. Scenario
    This scenario makes sure we take fresh data and write it to the given folder, thus
    we can run just another test afterwards as no old data is used
    """
    collect_dwd_data(
        station_ids=[1],
        parameter=Parameter.CLIMATE_SUMMARY,
        time_resolution=TimeResolution.DAILY,
        period_type=PeriodType.HISTORICAL,
        folder=test_folder,
        prefer_local=False,
        write_file=True,
        tidy_data=False,
        create_new_file_index=False,
    ).equals(file)

    """
    2. Scenario
    This scenario tries to get the data from the given folder. This data was placed by
    the first test and is now restored
    """
    collect_dwd_data(
        station_ids=[1],
        parameter=Parameter.CLIMATE_SUMMARY,
        time_resolution=TimeResolution.DAILY,
        period_type=PeriodType.HISTORICAL,
        folder=test_folder,
        prefer_local=True,
        write_file=True,
        tidy_data=False,
        create_new_file_index=False,
    ).equals(file)

    # Remove storage folder
    rmtree(test_folder)

    # Have to place an assert afterwards to ensure that above function is executed
    assert True


@patch(
    "wetterdienst.data_collection.restore_dwd_data",
    mock.MagicMock(return_value=pd.DataFrame()),
)
@patch(
    "wetterdienst.data_collection.create_file_list_for_dwd_server",
    mock.MagicMock(return_value=pd.DataFrame(columns=[DWDMetaColumns.FILENAME.value])),
)
def test_collect_dwd_data_empty():
    """ Test for data collection with no available data """

    """
    1. Scenario
    Test for request where no data is available
    """
    assert collect_dwd_data(
        station_ids=[1],
        parameter=Parameter.CLIMATE_SUMMARY,
        time_resolution=TimeResolution.DAILY,
        period_type=PeriodType.HISTORICAL,
        folder="",
        prefer_local=True,
        write_file=False,
        tidy_data=False,
        create_new_file_index=False,
    ).empty


@pytest.mark.remote
def test_collect_daily_vanilla():
    """ Test for data collection with real data """

    data = collect_dwd_data(
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

    data = collect_dwd_data(
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
