""" tests for file index creation """
import pytest
from pandas import Timestamp

from python_dwd.enumerations.column_names_enumeration import DWDMetaColumns
from python_dwd.indexing.meta_index_creation import create_meta_index_for_dwd_data, reset_meta_index_cache
from python_dwd.enumerations.parameter_enumeration import Parameter
from python_dwd.enumerations.time_resolution_enumeration import TimeResolution
from python_dwd.enumerations.period_type_enumeration import PeriodType


@pytest.mark.remote
def test_meta_index_creation():
    reset_meta_index_cache()

    # Existing combination of parameters
    meta_index = create_meta_index_for_dwd_data(
        Parameter.CLIMATE_SUMMARY, TimeResolution.DAILY, PeriodType.HISTORICAL)

    assert not meta_index.empty

    reset_meta_index_cache()

    meta_index2 = create_meta_index_for_dwd_data(
        Parameter.CLIMATE_SUMMARY, TimeResolution.DAILY, PeriodType.HISTORICAL)

    assert meta_index.equals(meta_index2)

    # todo: replace IndexError with UrlError/WrongSetOfParametersError
    with pytest.raises(IndexError):
        create_meta_index_for_dwd_data(
            Parameter.CLIMATE_SUMMARY, TimeResolution.MINUTE_1, PeriodType.HISTORICAL)


@pytest.mark.remote
def test_meta_index_1mph_creation():
    reset_meta_index_cache()
    meta_index_1mph = create_meta_index_for_dwd_data(
        Parameter.PRECIPITATION, TimeResolution.MINUTE_1, PeriodType.HISTORICAL)

    assert meta_index_1mph.loc[meta_index_1mph[DWDMetaColumns.STATION_ID.value] == 1048, :].values.tolist() == \
        [[1048, Timestamp("19260401"), Timestamp("20200623"), 227.0,
         51.1280, 13.7543, "Dresden-Klotzsche"]]
