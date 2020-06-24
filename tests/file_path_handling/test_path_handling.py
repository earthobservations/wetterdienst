from pathlib import PurePosixPath

from python_dwd.enumerations.parameter_enumeration import Parameter
from python_dwd.enumerations.period_type_enumeration import PeriodType
from python_dwd.enumerations.time_resolution_enumeration import TimeResolution
from python_dwd.file_path_handling.path_handling import build_local_filepath_for_station_data, build_index_path


def test_build_local_filepath_for_station_data():
    local_filepath = build_local_filepath_for_station_data("dwd_data")

    assert "/".join(local_filepath.as_posix().split("/")[-3:]) == \
           f"dwd_data/station_data/dwd_station_data.h5"


def test_build_index_path():
    path = build_index_path(Parameter.CLIMATE_SUMMARY, TimeResolution.DAILY, PeriodType.HISTORICAL)
    assert path == PurePosixPath(
        "climate_environment/CDC/observations_germany/climate/daily/kl/historical")
