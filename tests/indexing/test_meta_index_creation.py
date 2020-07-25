""" tests for file index creation """
import requests
import pytest
from pandas import Timestamp

from wetterdienst.enumerations.column_names_enumeration import DWDMetaColumns
from wetterdienst.indexing.meta_index_creation import (
    create_meta_index_for_dwd_data,
    reset_meta_index_cache,
)
from wetterdienst.enumerations.parameter_enumeration import Parameter
from wetterdienst.enumerations.time_resolution_enumeration import TimeResolution
from wetterdienst.enumerations.period_type_enumeration import PeriodType


@pytest.mark.remote
def test_meta_index_creation():
    reset_meta_index_cache()

    # Existing combination of parameters
    meta_index = create_meta_index_for_dwd_data(
        Parameter.CLIMATE_SUMMARY, TimeResolution.DAILY, PeriodType.HISTORICAL
    )

    assert not meta_index.empty

    reset_meta_index_cache()

    meta_index2 = create_meta_index_for_dwd_data(
        Parameter.CLIMATE_SUMMARY, TimeResolution.DAILY, PeriodType.HISTORICAL
    )

    assert meta_index.equals(meta_index2)

    # todo: replace IndexError with UrlError/WrongSetOfParametersError
    with pytest.raises(requests.exceptions.HTTPError):
        create_meta_index_for_dwd_data(
            Parameter.CLIMATE_SUMMARY, TimeResolution.MINUTE_1, PeriodType.HISTORICAL
        )


@pytest.mark.remote
def test_meta_index_1mph_creation():
    reset_meta_index_cache()
    meta_index_1mph = create_meta_index_for_dwd_data(
        Parameter.PRECIPITATION, TimeResolution.MINUTE_1, PeriodType.HISTORICAL
    )

    assert meta_index_1mph.loc[
        meta_index_1mph[DWDMetaColumns.STATION_ID.value] == 3, :
    ].values.tolist() == [
        [
            3,
            Timestamp("18910101"),
            Timestamp("20120406"),
            202.00,
            50.7827,
            6.0941,
            "Aachen",
            "Nordrhein-Westfalen",
        ]
    ]
