""" Tests for data_collection """
import mock
import numpy
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
from wetterdienst.data_collection import collect_dwd_data

# Create folder for storage test
test_folder = Path(Path(__file__).parent.absolute() / "dwd_data")
test_folder.mkdir(parents=True, exist_ok=True)

fixtures_dir = Path(__file__, "../").resolve().absolute() / "fixtures"

# Setting parameters for tests
station_ids = [1]
parameter = Parameter.CLIMATE_SUMMARY
time_resolution = TimeResolution.DAILY
period_type = PeriodType.HISTORICAL
create_new_file_index = False

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
    mock.MagicMock(return_value=pd.DataFrame({DWDMetaColumns.FILENAME.value: [filename]}))
)
@patch(
    "wetterdienst.data_collection.download_dwd_data_parallel",
    mock.MagicMock(return_value=[(filename, BytesIO(csv_file.read().encode()))])
)
def test_collect_dwd_data():
    """ Test for data collection """
    """
    1. Scenario
    This scenario makes sure we take fresh data and write it to the given folder, thus we can run
    just another test afterwards as no old data is used
    """
    collect_dwd_data(
        station_ids=station_ids,
        parameter=parameter,
        time_resolution=time_resolution,
        period_type=period_type,
        folder=test_folder,
        prefer_local=False,
        write_file=True,
        create_new_file_index=create_new_file_index
    ).equals(file)

    """
    2. Scenario
    This scenario tries to get the data from the given folder. This data was placed by the first test
    and is now restored
    """
    collect_dwd_data(
        station_ids=station_ids,
        parameter=parameter,
        time_resolution=time_resolution,
        period_type=period_type,
        folder=test_folder,
        prefer_local=True,
        write_file=True,
        create_new_file_index=create_new_file_index
    ).equals(file)

    # Remove storage folder
    rmtree(test_folder)

    # Have to place an assert afterwards to ensure that above function is executed
    assert True


@patch(
    "wetterdienst.data_collection.restore_dwd_data",
    mock.MagicMock(return_value=pd.DataFrame())
)
@patch(
    "wetterdienst.data_collection.create_file_list_for_dwd_server",
    mock.MagicMock(return_value=pd.DataFrame(columns=[DWDMetaColumns.FILENAME.value]))
)
def test_collect_dwd_data_empty():
    """ Test for data collection with no available data """

    """
    1. Scenario
    Test for request where no data is available
    """
    assert collect_dwd_data(
        station_ids=station_ids,
        parameter=parameter,
        time_resolution=time_resolution,
        period_type=period_type,
        folder="",
        prefer_local=True,
        write_file=False,
        create_new_file_index=create_new_file_index
    ).empty


@pytest.mark.remote
def test_collect_daily_vanilla():
    """ Test for data collection with real data """

    data = collect_dwd_data(
        station_ids=[1048],
        parameter=Parameter.CLIMATE_SUMMARY,
        time_resolution=TimeResolution.DAILY,
        period_type=PeriodType.RECENT
    )

    assert list(data.columns.values) == [
        'STATION_ID',
        'DATE',
        'QN_3',
        'FX',
        'FM',
        'QN_4',
        'RSK',
        'RSKF',
        'SDK',
        'SHK_TAG',
        'NM',
        'VPM',
        'PM',
        'TMK',
        'UPM',
        'TXK',
        'TNK',
        'TGK',
    ]

    assert isinstance(data.iloc[0]['QN_3'], numpy.int64)
    assert isinstance(data.iloc[0]['QN_4'], numpy.int64)
    assert isinstance(data.iloc[0]['RSKF'], numpy.int64)


@pytest.mark.remote
def test_collect_daily_humanized():
    """ Test for data collection with real data and humanized column names """

    data = collect_dwd_data(
        station_ids=[1048],
        parameter=Parameter.CLIMATE_SUMMARY,
        time_resolution=TimeResolution.DAILY,
        period_type=PeriodType.RECENT,
        humanize_column_names=True
    )

    assert list(data.columns.values) == [
        'STATION_ID',
        'DATE',
        'QN_3',
        'WIND_GUST_MAX',
        'WIND_VELOCITY',
        'QN_4',
        'PRECIPITATION_HEIGHT',
        'PRECIPITATION_FORM',
        'SUNSHINE_DURATION',
        'SNOW_DEPTH',
        'CLOUD_COVER',
        'VAPOR_PRESSURE',
        'PRESSURE',
        'TEMPERATURE',
        'HUMIDITY',
        'TEMPERATURE_MAX_200',
        'TEMPERATURE_MIN_200',
        'TEMPERATURE_MIN_005',
    ]

    assert isinstance(data.iloc[0]['PRECIPITATION_FORM'], numpy.int64)


@pytest.mark.remote
def test_collect_hourly_vanilla():
    """ Test for data collection with real data """

    data = collect_dwd_data(
        station_ids=[1048],
        parameter=Parameter.TEMPERATURE_AIR,
        time_resolution=TimeResolution.HOURLY,
        period_type=PeriodType.RECENT
    )

    assert list(data.columns.values) == [
        'STATION_ID',
        'DATE',
        'QN_9',
        'TT_TU',
        'RF_TU',
    ]

    assert isinstance(data.iloc[0]['QN_9'], numpy.int64)
