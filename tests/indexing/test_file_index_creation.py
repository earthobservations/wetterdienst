""" tests for file index creation """
import pytest
import requests

from python_dwd.enumerations.column_names_enumeration import DWDMetaColumns
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
        Parameter.CLIMATE_SUMMARY, TimeResolution.DAILY, PeriodType.RECENT)

    assert not file_index.empty

    reset_file_index_cache()

    file_index2 = create_file_index_for_dwd_server(
        Parameter.CLIMATE_SUMMARY, TimeResolution.DAILY, PeriodType.RECENT)

    assert file_index.equals(file_index2)

    assert file_index.loc[
               file_index[DWDMetaColumns.STATION_ID.value] == 1048,
               DWDMetaColumns.FILENAME.value
           ].values.tolist() == ["daily/kl/recent/tageswerte_KL_01048_akt.zip"]

    with pytest.raises(requests.exceptions.HTTPError):
        create_file_index_for_dwd_server(
            Parameter.CLIMATE_SUMMARY, TimeResolution.MINUTE_1, PeriodType.HISTORICAL)
