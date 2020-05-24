""" Tests for data_collection """
import mock
from mock import patch
from pathlib import Path
import pandas as pd
from io import StringIO

from python_dwd.enumerations.column_names_enumeration import DWDColumns
from python_dwd.enumerations.parameter_enumeration import Parameter
from python_dwd.enumerations.time_resolution_enumeration import TimeResolution
from python_dwd.enumerations.period_type_enumeration import PeriodType
from python_dwd.data_collection import collect_dwd_data

fixtures_dir = Path(__file__, "../").resolve().absolute() / "fixtures"

# Setting parameters
station_ids = [1]
parameter = Parameter.CLIMATE_SUMMARY
time_resolution = TimeResolution.DAILY
period_type = PeriodType.HISTORICAL
folder = ""
parallel_download = False
write_file = False
create_new_filelist = False

# Set filename for mock
filename = "tageswerte_KL_00001_19370101_19860630_hist.zip"

# Loading test data
file = pd.read_json(fixtures_dir / "FIXED_STATIONDATA.JSON")
file_in_bytes = StringIO()
file.to_csv(file_in_bytes, sep=";")
file_in_bytes.seek(0)


@patch(
    "python_dwd.file_path_handling.file_list_creation.create_file_list_for_dwd_server",
    mock.MagicMock(return_value=pd.DataFrame({DWDColumns.FILENAME.value: [filename]}))
)
@patch(
    "python_dwd.download.download.download_dwd_data",
    mock.MagicMock(return_value=(filename, file_in_bytes))
)
def test_collect_dwd_data_online():
    # test for no local interaction
    collect_dwd_data(
        station_ids=station_ids,
        parameter=parameter,
        time_resolution=time_resolution,
        period_type=period_type,
        folder=folder,
        prefer_local=False,
        parallel_download=parallel_download,
        write_file=write_file,
        create_new_filelist=create_new_filelist
    ).equals(file)

# @todo implement further tests
