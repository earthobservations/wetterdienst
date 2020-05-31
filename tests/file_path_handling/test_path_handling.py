from python_dwd.constants.metadata import STATIONDATA_NAME, H5_FORMAT
from python_dwd.file_path_handling.path_handling import build_local_filepath_for_station_data


def test_build_local_filepath_for_station_data():
    local_filepath = build_local_filepath_for_station_data("dwd_data")

    assert "/".join(local_filepath.as_posix().split("/")[-3:]) == \
           f"dwd_data/{STATIONDATA_NAME}/{STATIONDATA_NAME}{H5_FORMAT}"
