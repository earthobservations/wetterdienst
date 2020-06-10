""" Tests for data_collection """
import mock
from mock import patch
from pathlib import Path
import pandas as pd
from io import StringIO
from shutil import rmtree

from python_dwd.enumerations.column_names_enumeration import DWDColumns
from python_dwd.enumerations.parameter_enumeration import Parameter
from python_dwd.enumerations.time_resolution_enumeration import TimeResolution
from python_dwd.enumerations.period_type_enumeration import PeriodType
from python_dwd.data_collection import collect_dwd_data


fixtures_dir = Path(__file__, "../").resolve().absolute() / "fixtures"

# Setting parameters for tests
station_ids = [1]
parameter = Parameter.CLIMATE_SUMMARY
time_resolution = TimeResolution.DAILY
period_type = PeriodType.HISTORICAL
parallel_download = False
create_new_filelist = False

# Set filename for mock
filename = "tageswerte_KL_00001_19370101_19860630_hist.zip"

# Loading test data
file = pd.read_json(fixtures_dir / "FIXED_STATIONDATA.JSON")

# Prepare csv for regular "downloading" test
csv_file = StringIO()
file.to_csv(csv_file, sep=";")
csv_file.seek(0)


@patch(
    "python_dwd.data_collection.create_file_list_for_dwd_server",
    mock.MagicMock(return_value=pd.DataFrame({DWDColumns.FILENAME.value: [filename]}))
)
@patch(
    "python_dwd.data_collection.download_dwd_data",
    mock.MagicMock(return_value=[(filename, csv_file)])
)
def test_collect_dwd_data():
    """ Test for data collection """

    # Create folder for storage test
    test_folder = Path(Path(__file__).parent.absolute() / "dwd_data")
    test_folder.mkdir(parents=True, exist_ok=True)

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
        parallel_download=parallel_download,
        write_file=True,
        create_new_filelist=create_new_filelist
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
        parallel_download=parallel_download,
        write_file=True,
        create_new_filelist=create_new_filelist
    ).equals(file)

    # Remove storage folder
    rmtree(test_folder)

    # Have to place an assert afterwards to ensure that above function is executed
    assert True


@patch(
    "python_dwd.data_collection.restore_dwd_data",
    mock.MagicMock(return_value=(False, pd.DataFrame()))
)
@patch(
    "python_dwd.data_collection.create_file_list_for_dwd_server",
    mock.MagicMock(return_value=pd.DataFrame(None, columns=[DWDColumns.FILENAME.value]))
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
        parallel_download=parallel_download,
        write_file=False,
        create_new_filelist=create_new_filelist
    ).empty
