import pytest
from pandas import Timestamp

from python_dwd import reset_meta_index_cache
from python_dwd.enumerations.column_names_enumeration import DWDMetaColumns
from python_dwd.parse_metadata import metadata_for_dwd_data
from python_dwd.enumerations.parameter_enumeration import Parameter
from python_dwd.enumerations.period_type_enumeration import PeriodType
from python_dwd.enumerations.time_resolution_enumeration import TimeResolution


def test_metadata_for_dwd_data():
    reset_meta_index_cache()

    # Existing combination of parameters
    metadata = metadata_for_dwd_data(
        Parameter.CLIMATE_SUMMARY, TimeResolution.DAILY, PeriodType.HISTORICAL)

    assert not metadata.empty

    reset_meta_index_cache()

    metadata2 = metadata_for_dwd_data(
        Parameter.CLIMATE_SUMMARY, TimeResolution.DAILY, PeriodType.HISTORICAL)

    assert metadata.equals(metadata2)

    assert metadata.loc[metadata[DWDMetaColumns.STATION_ID.value] == 1048, :].values.tolist() == \
        [[1048, Timestamp("19340101"), Timestamp("20200622"), 227,
         51.1280, 13.7543, "Dresden-Klotzsche", "Sachsen", True]]

    # todo: replace IndexError with UrlError/WrongSetOfParametersError
    with pytest.raises(IndexError):
        metadata_for_dwd_data(
            Parameter.CLIMATE_SUMMARY, TimeResolution.MINUTE_1, PeriodType.HISTORICAL)
