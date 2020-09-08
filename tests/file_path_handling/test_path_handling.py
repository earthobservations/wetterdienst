from pathlib import PurePosixPath, PosixPath
from datetime import datetime
import pytest

from wetterdienst.constants.metadata import DWD_FOLDER_MAIN
from wetterdienst.constants.access_credentials import DWDCDCBase
from wetterdienst.enumerations.parameter_enumeration import Parameter
from wetterdienst.enumerations.period_type_enumeration import PeriodType
from wetterdienst.enumerations.time_resolution_enumeration import TimeResolution
from wetterdienst.file_path_handling.path_handling import (
    build_local_filepath_for_station_data,
    build_path_to_parameter,
    build_dwd_directory_data_path,
    list_files_of_dwd_server,
    build_local_filepath_for_radar,
)


def test_build_local_filepath_for_radar():
    assert PosixPath('/home/dlassahn/projects/forecast-system/wetterdienst/'
                     'dwd_data/dx/5_minutes/dx_5_minutes_202001011215') == \
           build_local_filepath_for_radar(
               Parameter.DX_REFLECTIVITY,
               datetime(2020, 1, 1, 12, 15),
               DWD_FOLDER_MAIN,
               TimeResolution.MINUTE_5)


def test_build_local_filepath_for_station_data():
    local_filepath = build_local_filepath_for_station_data("dwd_data")

    assert (
            "/".join(local_filepath.as_posix().split("/")[-3:])
            == "dwd_data/station_data/dwd_station_data.h5"
    )


def test_build_index_path():
    path = build_path_to_parameter(
        Parameter.CLIMATE_SUMMARY, TimeResolution.DAILY, PeriodType.HISTORICAL
    )
    assert path == PurePosixPath("daily/kl/historical")


def test_build_climate_observations_path():
    assert (
            build_dwd_directory_data_path("abc", dwd_base=DWDCDCBase.CLIMATE_OBSERVATIONS)
            == "https://opendata.dwd.de/climate_environment/CDC/"
               "observations_germany/climate/abc"
    )


@pytest.mark.remote
def test_list_files_of_climate_observations():
    files_server = list_files_of_dwd_server(
        "annual/kl/recent/", recursive=False, dwd_base=DWDCDCBase.CLIMATE_OBSERVATIONS
    )

    assert "annual/kl/recent/jahreswerte_KL_01048_akt.zip" in files_server
