import pytest
import requests
from pandas import Timestamp

from wetterdienst import reset_meta_index_cache
from wetterdienst.enumerations.column_names_enumeration import DWDMetaColumns
from wetterdienst.parse_metadata import metadata_for_dwd_data
from wetterdienst.enumerations.parameter_enumeration import Parameter
from wetterdienst.enumerations.period_type_enumeration import PeriodType
from wetterdienst.enumerations.time_resolution_enumeration import TimeResolution


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

    assert metadata.loc[metadata[DWDMetaColumns.STATION_ID.value] == 1, :].values.tolist() == \
        [[1, Timestamp("19370101"), Timestamp("19860630"), 478.0,
         47.8413, 8.8493, "Aach", "Baden-Württemberg", True]]

    # todo: replace IndexError with UrlError/WrongSetOfParametersError
    with pytest.raises(requests.exceptions.HTTPError):
        metadata_for_dwd_data(
            Parameter.CLIMATE_SUMMARY, TimeResolution.MINUTE_1, PeriodType.HISTORICAL)
