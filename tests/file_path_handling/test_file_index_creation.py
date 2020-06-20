from python_dwd.file_path_handling.file_index_creation import create_file_index_for_dwd_server, \
    reset_file_index_cache
from python_dwd.enumerations.parameter_enumeration import Parameter
from python_dwd.enumerations.time_resolution_enumeration import TimeResolution
from python_dwd.enumerations.period_type_enumeration import PeriodType


def test_file_index_creation():
    file_index = create_file_index_for_dwd_server(
        Parameter.CLIMATE_SUMMARY, TimeResolution.DAILY, PeriodType.HISTORICAL)

    assert not file_index.empty

    assert create_file_index_for_dwd_server.cache_info().currsize == 1

    reset_file_index_cache()

    assert create_file_index_for_dwd_server.cache_info().currsize == 0

    file_index2 = create_file_index_for_dwd_server(
        Parameter.CLIMATE_SUMMARY, TimeResolution.DAILY, PeriodType.HISTORICAL)

    assert file_index.equals(file_index2)
