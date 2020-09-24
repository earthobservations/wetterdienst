import pytest

from wetterdienst.enumerations.parameter_enumeration import Parameter
from wetterdienst.enumerations.period_type_enumeration import PeriodType
from wetterdienst.enumerations.time_resolution_enumeration import TimeResolution
from wetterdienst.file_path_handling.path_handling import (
    build_local_filepath_for_station_data,
    build_path_to_parameter,
    list_files_of_dwd_server,
)


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
    assert path == "daily/kl/historical/"


@pytest.mark.remote
def test_list_files_of_climate_observations():
    files_server = list_files_of_dwd_server(
        "https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/"
        "annual/kl/recent",
        recursive=False,
    )

    assert (
        "https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/"
        "annual/kl/recent/jahreswerte_KL_01048_akt.zip" in files_server
    )
