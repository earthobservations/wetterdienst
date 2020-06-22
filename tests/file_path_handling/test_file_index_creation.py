""" tests for file index creation """
import pytest

from python_dwd.indexing.file_index_creation import create_file_index_for_dwd_server, \
    reset_file_index_cache
from python_dwd.enumerations.parameter_enumeration import Parameter
from python_dwd.enumerations.time_resolution_enumeration import TimeResolution
from python_dwd.enumerations.period_type_enumeration import PeriodType


@pytest.mark.remote
def test_file_index_creation():
    reset_file_index_cache()

    # Existing combination of parameters
    file_index = create_file_index_for_dwd_server(
        Parameter.CLIMATE_SUMMARY, TimeResolution.DAILY, PeriodType.HISTORICAL)

    assert not file_index.empty

    reset_file_index_cache()

    file_index2 = create_file_index_for_dwd_server(
        Parameter.CLIMATE_SUMMARY, TimeResolution.DAILY, PeriodType.HISTORICAL)

    assert file_index.equals(file_index2)

    # todo: replace with pytest.raises for wrong parameters
    file_index_false = create_file_index_for_dwd_server(
        Parameter.CLIMATE_SUMMARY, TimeResolution.MINUTE_1, PeriodType.HISTORICAL)

    assert file_index_false.empty
